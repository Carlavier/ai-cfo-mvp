# data_sync.py - API Data Sync Script
import os
from pathlib import Path
import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from database_module import DatabaseManager
from dotenv import load_dotenv
import pandas as pd
import streamlit as st
import webbrowser
import urllib.parse
from requests.auth import HTTPBasicAuth

# Load environment early so other modules in this file see vars
load_dotenv(override=True)

# Try to import real API clients
try:
    import plaid
    from plaid.api import plaid_api
    from plaid.model.transactions_get_request import TransactionsGetRequest
    from plaid.model.accounts_get_request import AccountsGetRequest
    from plaid.configuration import Configuration
    from plaid.api_client import ApiClient

    PLAID_AVAILABLE = True
except ImportError:
    PLAID_AVAILABLE = False

try:
    from intuitlib.client import AuthClient
    from quickbooks import QuickBooks
    from quickbooks.objects import Invoice, Bill, Account

    QB_AVAILABLE = True
except ImportError:
    QB_AVAILABLE = False


# ------------------------- QuickBooks REST helpers -------------------------
def _qb_base_url(qb_tokens: Dict) -> str:
    return (
        f"https://sandbox-quickbooks.api.intuit.com/v3/company/{qb_tokens['realm_id']}"
    )


def qb_request(
    method: str, endpoint: str, qb_tokens: Dict, payload: Optional[Dict] = None
) -> Dict:
    """Perform a QuickBooks REST API request and return JSON or raise."""
    url = f"{_qb_base_url(qb_tokens)}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {qb_tokens['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    resp = requests.request(
        method.upper(), url, headers=headers, json=payload, timeout=60
    )
    if 200 <= resp.status_code < 300:
        try:
            return resp.json()
        except Exception:
            return {}
    raise Exception(f"QuickBooks API error {resp.status_code}: {resp.text}")


def qb_query(qb_tokens: Dict, q: str) -> Dict:
    # Escape single-quotes for QBO SQL
    q_escaped = q.replace("'", "''")
    endpoint = f"query?query={urllib.parse.quote(q_escaped)}&minorversion=70"
    return qb_request("GET", endpoint, qb_tokens)


def qb_get_account_by_name(qb_tokens: Dict, name: str) -> Optional[Dict]:
    data = qb_query(
        qb_tokens,
        f"select Id, Name, AccountType, AccountSubType from Account where Name = '{name}'",
    )
    return (data.get("QueryResponse", {}).get("Account") or [None])[0]


def qb_create_account(
    qb_tokens: Dict, name: str, account_type: str, subtype: Optional[str] = None
) -> Dict:
    payload = {"Name": name, "AccountType": account_type}
    if subtype:
        payload["AccountSubType"] = subtype
    data = qb_request("POST", "account?minorversion=70", qb_tokens, payload)
    return data.get("Account", payload)


def ensure_qb_account(
    qb_tokens: Dict, name: str, account_type: str, subtype: Optional[str] = None
) -> Dict:
    acc = qb_get_account_by_name(qb_tokens, name)
    if acc:
        return acc
    return qb_create_account(qb_tokens, name, account_type, subtype)


def map_plaid_category_to_qb(
    category: str, is_income: bool
) -> Tuple[str, str, Optional[str]]:
    """Return (account_name, account_type, subtype) for QuickBooks."""
    if is_income:
        return ("Sales", "Income", "SalesOfProductIncome")
    cat = (category or "").lower()
    mapping = {
        "advertising": ("Advertising", "Expense", "Advertising"),
        "marketing": ("Advertising", "Expense", "Advertising"),
        "travel": ("Travel", "Expense", "Travel"),
        "restaurant": ("Meals and Entertainment", "Expense", "MealsAndEntertainment"),
        "software": ("Software Subscriptions", "Expense", "OfficeSupplies"),
        "utilities": ("Utilities", "Expense", "Utilities"),
        "rent": ("Rent or Lease", "Expense", "RentOrLeaseOfBuildings"),
        "office": ("Office Supplies", "Expense", "OfficeSupplies"),
        "insurance": ("Insurance", "Expense", "Insurance"),
        "fee": ("Bank Charges", "Expense", "BankCharges"),
        "service": ("Legal & Professional Fees", "Expense", "LegalProfessionalFees"),
    }
    for key, val in mapping.items():
        if key in cat:
            return val
    return ("Uncategorized Expense", "Expense", "UncategorizedExpense")


class DataSyncManager:
    def __init__(self):
        self.db = DatabaseManager()
        self.setup_plaid()
        self.setup_quickbooks()

    def setup_plaid(self):
        """Setup Plaid client"""
        if not PLAID_AVAILABLE:
            print("⚠️ Plaid not available. Install: pip install plaid-python")
            self.plaid_client = None
            return

        client_id = os.getenv("PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"]
        secret = os.getenv("PLAID_SECRET") or st.secrets["PLAID_SECRET"]
        # Normalize env and map to correct constants
        env_name = (
            os.getenv("PLAID_ENV", "sandbox").capitalize()
            or str(st.secrets["PLAID_ENV"] or "sandbox").capitalize()
        )

        if not client_id or not secret:
            print("⚠️ Plaid credentials not found. Set PLAID_CLIENT_ID and PLAID_SECRET")
            self.plaid_client = None
            return

        try:

            env_map = {
                "sandbox": plaid.Environment.Sandbox,
                "development": plaid.Environment.Sandbox,
                "production": plaid.Environment.Sandbox,
            }

            host = env_map.get(env_name, plaid.Environment.Sandbox)

            configuration = Configuration(
                host=host,
                api_key={"clientId": client_id, "secret": secret},
            )
            api_client = ApiClient(configuration)
            self.plaid_client = plaid_api.PlaidApi(api_client)
            print("✅ Plaid client initialized")
        except Exception as e:
            print(f"❌ Plaid setup failed: {e}")
            self.plaid_client = None

    def setup_quickbooks(self):
        """Setup QuickBooks client"""
        # Ensure attribute exists to avoid AttributeError downstream
        self.auth_client = None
        if not QB_AVAILABLE:
            print(
                "⚠️ QuickBooks not available. Install: pip install quickbooks-python3 intuitlib"
            )
            self.qb_client = None
            return

        client_id = os.getenv("QB_CLIENT_ID") or st.secrets["QB_CLIENT_ID"]
        secret = os.getenv("QB_CLIENT_SECRET") or st.secrets["QB_CLIENT_SECRET"]
        base_url = os.getenv("APP_BASE_URL") or st.secrets["APP_BASE_URL"]
        qb_redirect_uri = (
            os.getenv("QB_CLIENT_REDIRECT_URL") or st.secrets["QB_CLIENT_REDIRECT_URL"]
        )

        if not qb_redirect_uri:
            base = (base_url or "http://localhost:8501").rstrip("/")
            qb_redirect_uri = os.getenv(
                "APP_REDIRECT_URI", f"{base}/"
            ) or st.secrets.get("APP_REDIRECT_URI", f"{base}/")

        if not client_id or not secret:
            print(
                "⚠️ QuickBooks credentials not found. Set QB_CLIENT_ID and QB_CLIENT_SECRET"
            )
            self.qb_client = None
            self.auth_client = None
            return

        try:
            self.auth_client = AuthClient(
                client_id=client_id,
                client_secret=secret,
                environment="Sandbox",
                redirect_uri=qb_redirect_uri,
            )

            print("✅ QuickBooks client initialized")
        except Exception as e:
            print(f"❌ QuickBooks setup failed: {e}")
            self.qb_client = None
            self.auth_client = None


def sync_plaid_data(company_id: int):
    """Sync Plaid banking data for a company"""
    sync_manager = DataSyncManager()
    from mock_data import seed_mock_plaid

    if not sync_manager.plaid_client:
        print("❌ Plaid client not available — seeding mock banking data")
        acc_count, tx_count = seed_mock_plaid(sync_manager.db, company_id)
        sync_manager.db.log_sync(
            company_id, "plaid", "mock_seed", acc_count + tx_count, True
        )
        print(
            f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions"
        )
        return True

    try:
        # Get stored access token for company
        access_token = get_company_plaid_token(company_id)

        if not access_token:
            print(
                f"❌ No Plaid access token found for company {company_id} — using mock data"
            )
            acc_count, tx_count = seed_mock_plaid(sync_manager.db, company_id)
            sync_manager.db.log_sync(
                company_id, "plaid", "mock_seed", acc_count + tx_count, True
            )
            print(
                f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions"
            )
            return True

        print(f"🔄 Syncing Plaid data for company {company_id}...")

        # Sync accounts
        accounts_synced = sync_plaid_accounts(sync_manager, company_id, access_token)

        # Sync transactions
        transactions_synced = sync_plaid_transactions(
            sync_manager, company_id, access_token
        )

        # Log sync
        sync_manager.db.log_sync(
            company_id,
            "plaid",
            "full_sync",
            accounts_synced + transactions_synced,
            True,
        )

        print(
            f"✅ Plaid sync completed: {accounts_synced} accounts, {transactions_synced} transactions"
        )
        return True

    except Exception as e:
        print(f"❌ Plaid sync failed: {e} — falling back to mock data")
        try:
            acc_count, tx_count = seed_mock_plaid(sync_manager.db, company_id)
            sync_manager.db.log_sync(
                company_id, "plaid", "mock_seed", acc_count + tx_count, True
            )
            print(
                f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions"
            )
            return True
        except Exception as inner:
            print(f"❌ Mock Plaid seeding failed: {inner}")
            sync_manager.db.log_sync(
                company_id,
                "plaid",
                "full_sync",
                0,
                False,
                f"api_error={e}; mock_error={inner}",
            )
            return False


def sync_plaid_accounts(
    sync_manager: DataSyncManager, company_id: int, access_token: str
) -> int:
    """Sync Plaid accounts"""
    request = AccountsGetRequest(access_token=access_token)
    response = sync_manager.plaid_client.accounts_get(request)

    accounts_synced = 0

    # Handle both dict-like response and Plaid response objects
    accounts = (
        response.get("accounts") if hasattr(response, "get") else response.accounts
    )

    for account in accounts:
        # Convert Plaid objects to dict-like access if needed
        if hasattr(account, "account_id"):
            # Plaid response object
            account_data = {
                "company_id": company_id,
                "account_id": account.account_id,
                "name": account.name,
                "institution_name": getattr(account, "institution_name", ""),
                "type": (
                    str(account.type.value)
                    if hasattr(account.type, "value")
                    else str(account.type)
                ),
                "subtype": (
                    str(account.subtype.value)
                    if hasattr(account.subtype, "value")
                    else str(account.subtype)
                ),
                "current_balance": (
                    float(account.balances.current) if account.balances.current else 0.0
                ),
                "available_balance": (
                    float(account.balances.available)
                    if account.balances.available
                    else 0.0
                ),
                "mask": getattr(account, "mask", ""),
            }
        else:
            # Dict-like response
            account_data = {
                "company_id": company_id,
                "account_id": account["account_id"],
                "name": account["name"],
                "institution_name": account.get("institution_name", ""),
                "type": str(account["type"]),
                "subtype": str(account["subtype"]),
                "current_balance": (
                    float(account["balances"]["current"])
                    if account["balances"]["current"]
                    else 0.0
                ),
                "available_balance": (
                    float(account["balances"]["available"])
                    if account["balances"]["available"]
                    else 0.0
                ),
                "mask": account.get("mask", ""),
            }

        sync_manager.db.save_account(account_data)
        accounts_synced += 1

    return accounts_synced


def sync_plaid_transactions(
    sync_manager: DataSyncManager, company_id: int, access_token: str
) -> int:
    """Sync Plaid transactions"""
    # Get transactions for last 30 days
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date.date(),
        end_date=end_date.date(),
    )

    response = sync_manager.plaid_client.transactions_get(request)
    transactions_synced = 0

    # Handle both dict-like response and Plaid response objects
    transactions = (
        response.get("transactions")
        if hasattr(response, "get")
        else response.transactions
    )

    batch_candidates: List[Dict] = []
    local_accounts_cache: Dict[int, Dict] = {}

    for transaction in transactions:
        # Get local account ID
        if hasattr(transaction, "account_id"):
            # Plaid response object
            plaid_account_id = transaction.account_id

            local_account = sync_manager.db.get_account_by_plaid_id(
                company_id, plaid_account_id
            )

            if not local_account:
                continue

            # Convert date properly
            transaction_date = transaction.date
            if hasattr(transaction_date, "isoformat"):
                date_str = transaction_date.isoformat()
            else:
                date_str = str(transaction_date)

            transaction_data = {
                "account_id": local_account["id"],
                "transaction_id": transaction.transaction_id,
                "amount": -float(transaction.amount),  # Plaid uses positive for outflow
                "date": date_str,
                "merchant_name": getattr(transaction, "merchant_name", None)
                or getattr(transaction, "name", "Unknown"),
                "category": (
                    ",".join([str(cat) for cat in transaction.category])
                    if hasattr(transaction, "category") and transaction.category
                    else ""
                ),
                "pending": bool(getattr(transaction, "pending", False)),
            }
        else:
            # Dict-like response
            plaid_account_id = transaction["account_id"]
            local_account = sync_manager.db.get_account_by_plaid_id(
                company_id, plaid_account_id
            )

            if not local_account:
                continue

            transaction_data = {
                "account_id": local_account["id"],
                "transaction_id": transaction["transaction_id"],
                "amount": -float(
                    transaction["amount"]
                ),  # Plaid uses positive for outflow
                "date": str(transaction["date"]),
                "merchant_name": transaction.get("merchant_name", "Unknown"),
                "category": (
                    ",".join(transaction["category"]) if transaction["category"] else ""
                ),
                "pending": bool(transaction["pending"]),
            }

        if sync_manager.db.save_transaction(transaction_data) > 0:
            transactions_synced += 1
            # collect for QB push if not pending
            # if not transaction_data["pending"]:
            #     # Cache local account for later account name/ mask usage
            #     if (
            #         transaction_data["account_id"] not in local_accounts_cache
            #         and local_account
            #     ):
            #         local_accounts_cache[transaction_data["account_id"]] = local_account
            batch_candidates.append(transaction_data)

    # Batch push to QuickBooks if tokens present
    qb_tokens = get_company_qb_tokens(company_id)
    if qb_tokens and batch_candidates:
        # Break into chunks of 30 (QBO limit)
        for i in range(0, len(batch_candidates), 30):
            chunk = batch_candidates[i : i + 30]
            try:
                items = build_batch_journal_items(
                    qb_tokens, chunk, local_accounts_cache
                )
                if items:
                    resp = qb_batch_post(qb_tokens, items)
                    # Optional: inspect resp for faults and print brief summary
                    faults = []
                    for bri in resp.get("BatchItemResponse", []):
                        if "Fault" in bri:
                            faults.append(
                                {"bId": bri.get("bId"), "Fault": bri["Fault"]}
                            )
                    if faults:
                        print(f"⚠️ QB batch faults: {len(faults)} of {len(items)}")
            except Exception as e:
                print(f"⚠️ QB batch push failed: {e}")

    return transactions_synced


def fetch_qb_data(endpoint: str, qb_tokens: Dict):
    """Gọi QuickBooks API trả về JSON"""
    base_url = (
        f"https://sandbox-quickbooks.api.intuit.com/v3/company/{qb_tokens['realm_id']}"
    )
    url = f"{base_url}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {qb_tokens['access_token']}",
        "Accept": "application/json",
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise Exception(f"QuickBooks API error {resp.status_code}: {resp.text}")


# ------------------------- QuickBooks Batch JournalEntry -------------------------
def qb_find_journal_by_privatenote(
    qb_tokens: Dict, private_note: str
) -> Optional[Dict]:
    data = qb_query(
        qb_tokens, f"select Id from JournalEntry where PrivateNote = '{private_note}'"
    )
    items = data.get("QueryResponse", {}).get("JournalEntry", [])
    return items[0] if items else None


def build_qb_journal_entry_lines(
    amount: float, debit_acc: Dict, credit_acc: Dict, desc: str
) -> List[Dict]:
    amt = round(abs(float(amount)), 2)
    return [
        {
            "Description": desc,
            "Amount": amt,
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Debit",
                "AccountRef": {"value": debit_acc["Id"], "name": debit_acc.get("Name")},
            },
        },
        {
            "Description": desc,
            "Amount": amt,
            "DetailType": "JournalEntryLineDetail",
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": {
                    "value": credit_acc["Id"],
                    "name": credit_acc.get("Name"),
                },
            },
        },
    ]


def build_batch_journal_items(
    qb_tokens: Dict, txns: List[Dict], local_accounts_by_id: Dict[int, Dict]
) -> List[Dict]:
    """Create up to 30 BatchItemRequest for JournalEntry create.
    Each txn dict should have keys: transaction_id, date, amount, merchant_name, category, account_id (local DB id).
    """
    items: List[Dict] = []
    for t in txns:
        if len(items) >= 30:
            break
        privatenote = f"PLD:{t['transaction_id']}"
        # skip if exists
        if qb_find_journal_by_privatenote(qb_tokens, privatenote):
            continue

        local_acct = local_accounts_by_id.get(t["account_id"]) or {}
        bank_name_bits = [local_acct.get("name") or "Bank"]
        if local_acct.get("mask"):
            bank_name_bits.append(f"({local_acct['mask']})")
        bank_acc = ensure_qb_account(qb_tokens, " ".join(bank_name_bits), "Bank")

        is_income = float(t["amount"]) > 0
        qb_acc_name, qb_acc_type, qb_acc_subtype = map_plaid_category_to_qb(
            t.get("category", ""), is_income
        )
        cat_acc = ensure_qb_account(qb_tokens, qb_acc_name, qb_acc_type, qb_acc_subtype)

        # Determine debit/credit sides
        if is_income:
            debit_acc, credit_acc = bank_acc, cat_acc
        else:
            debit_acc, credit_acc = cat_acc, bank_acc

        journal = {
            "TxnDate": str(t["date"]),
            "PrivateNote": privatenote,
            "Line": build_qb_journal_entry_lines(
                t["amount"],
                debit_acc,
                credit_acc,
                t.get("merchant_name") or privatenote,
            ),
        }

        items.append(
            {
                "bId": privatenote,
                "operation": "create",
                "JournalEntry": journal,
            }
        )
    return items


def qb_batch_post(qb_tokens: Dict, batch_items: List[Dict]) -> Dict:
    payload = {"BatchItemRequest": batch_items}
    return qb_request("POST", "batch?minorversion=70", qb_tokens, payload)


def sync_qb_invoices(sync_manager, company_id: int, qb_tokens: Dict) -> int:
    """Lấy và lưu invoices từ QuickBooks"""
    data = fetch_qb_data("query?query=select * from Invoice", qb_tokens)
    invoices = data.get("QueryResponse", {}).get("Invoice", [])
    count = 0
    for inv in invoices:
        invoice_data = {
            "company_id": company_id,
            "qb_invoice_id": inv.get("Id"),
            "invoice_number": inv.get("DocNumber", ""),
            "customer_name": inv.get("CustomerRef", {}).get("name", "Unknown"),
            "amount": float(inv.get("TotalAmt", 0)),
            "balance": float(inv.get("Balance", 0)),
            "due_date": inv.get("DueDate"),
            "issue_date": inv.get("TxnDate"),
            "status": inv.get("TxnStatus", "pending"),
            "days_overdue": 0,
        }
        sync_manager.db.save_invoice(invoice_data)
        count += 1
    return count


def sync_qb_bills(sync_manager, company_id: int, qb_tokens: Dict) -> int:
    """Lấy và lưu bills từ QuickBooks"""
    data = fetch_qb_data("query?query=select * from Bill", qb_tokens)
    bills = data.get("QueryResponse", {}).get("Bill", [])
    count = 0
    for bill in bills:
        bill_data = {
            "company_id": company_id,
            "qb_bill_id": bill.get("Id"),
            "bill_number": bill.get("DocNumber", ""),
            "vendor_name": bill.get("VendorRef", {}).get("name", "Unknown"),
            "amount": float(bill.get("TotalAmt", 0)),
            "balance": float(bill.get("Balance", 0)),
            "due_date": bill.get("DueDate"),
            "category": "",
            "status": bill.get("TxnStatus", "pending"),
        }
        sync_manager.db.save_bill(bill_data)
        count += 1
    return count


def sync_quickbooks_data(company_id: int) -> bool:
    """Full sync QuickBooks data"""
    sync_manager = DataSyncManager()
    from mock_data import seed_mock_quickbooks

    qb_tokens = get_company_qb_tokens(company_id)
    if not qb_tokens:
        print(f"❌ No QuickBooks tokens for company {company_id}, using mock")
        inv, bill = seed_mock_quickbooks(sync_manager.db, company_id)
        sync_manager.db.log_sync(
            company_id, "quickbooks", "mock_seed", inv + bill, True
        )
        return True

    try:
        print(f"🔄 Sync QuickBooks data for company {company_id}...")

        invoices_synced = sync_qb_invoices(sync_manager, company_id, qb_tokens)
        bills_synced = sync_qb_bills(sync_manager, company_id, qb_tokens)

        sync_manager.db.log_sync(
            company_id, "quickbooks", "full_sync", invoices_synced + bills_synced, True
        )

        print(f"✅ Synced: {invoices_synced} invoices, {bills_synced} bills")
        return True
    except Exception as e:
        print(f"❌ Sync failed: {e}, falling back to mock")
        inv, bill = seed_mock_quickbooks(sync_manager.db, company_id)
        sync_manager.db.log_sync(
            company_id, "quickbooks", "mock_seed", inv + bill, True
        )
        return True


def plaid_base_url() -> str:
    env = (os.getenv("PLAID_ENV") or st.secrets["PLAID_ENV"] or "sandbox").lower()
    return {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }.get(env, "https://sandbox.plaid.com")


def get_company_plaid_token(company_id: int) -> str:
    """Get stored Plaid access token for company"""
    db = DatabaseManager()
    tokens = db.get_plaid_tokens(company_id)
    if not tokens:
        # No tokens found - create new ones and store in DB
        print(
            f"📝 No Plaid tokens found for company {company_id}, creating new ones..."
        )
        response = exchange_plaid_public_token()
        # Store the new tokens in database
        db.set_plaid_tokens(company_id, response["access_token"], response["item_id"])
        print(f"✅ Stored new Plaid tokens for company {company_id}")

        print(f"✅ Access Token { response["access_token"]}")

        return response["access_token"]
    return tokens.get("access_token") if tokens else None


def get_company_qb_tokens(company_id: int) -> Dict:
    """Get stored QuickBooks tokens for company"""
    # Check if QuickBooks tokens exist in session state
    if (
        "access_token" in st.session_state
        and "refresh_token" in st.session_state
        and "realm_id" in st.session_state
        and st.session_state["access_token"]
        and st.session_state["refresh_token"]
        and st.session_state["realm_id"]
    ):
        return {
            "access_token": st.session_state["access_token"],
            "refresh_token": st.session_state["refresh_token"],
            "realm_id": st.session_state["realm_id"],
        }

    # Nếu chưa có code thì chỉ hiển thị nút Connect
    CLIENT_ID = os.getenv("QB_CLIENT_ID") or st.secrets["QB_CLIENT_ID"]
    REDIRECT_URI = (
        os.getenv("QB_CLIENT_REDIRECT_URL") or st.secrets["QB_CLIENT_REDIRECT_URL"]
    )
    SCOPES = "com.intuit.quickbooks.accounting com.intuit.quickbooks.payment"
    STATE = "12345"

    auth_url = "https://appcenter.intuit.com/connect/oauth2?" + urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "scope": SCOPES,
            "redirect_uri": REDIRECT_URI,
            "state": STATE,
        }
    )

    st.markdown(f"[🔗 Connect to QuickBooks]({auth_url})")

    return None


def create_sandbox_public_token(
    institution_id: str = "ins_3",
    products: list[str] | None = None,
    options: dict | None = None,
) -> str:
    """Create a sandbox public_token using Plaid's /sandbox/public_token/create."""
    products = products or ["transactions"]  # include 'transactions' for tx sync
    payload = {
        "client_id": os.getenv("PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"],
        "secret": os.getenv("PLAID_SECRET") or st.secrets["PLAID_SECRET"],
        "institution_id": institution_id,
        "initial_products": products,
    }
    if options:
        payload["options"] = options

    url = f"{plaid_base_url()}/sandbox/public_token/create"
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    print(f"✅ Public  Token { data["public_token"]}")

    return data["public_token"]


def exchange_plaid_public_token_for_company(company_id: int, public_token: str) -> Dict:
    """Exchange public_token, store tokens for company in DB, and return stored record"""
    tokens = exchange_plaid_public_token(public_token)
    db = DatabaseManager()
    db.set_plaid_tokens(company_id, tokens["access_token"], tokens["item_id"])
    return db.get_plaid_tokens(company_id)


def exchange_plaid_public_token() -> Dict:
    """Call /item/public_token/exchange and return {'access_token','item_id'}"""

    public_token = create_sandbox_public_token()

    url = f"{plaid_base_url()}/item/public_token/exchange"
    payload = {
        "client_id": os.getenv("PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"],
        "secret": os.getenv("PLAID_SECRET") or st.secrets["PLAID_SECRET"],
        "public_token": public_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return {"access_token": data["access_token"], "item_id": data["item_id"]}


def invalidate_plaid_access_token(access_token: str) -> str:
    """Call /item/access_token/invalidate and return new_access_token"""
    url = f"{plaid_base_url()}/item/access_token/invalidate"
    payload = {
        "client_id": os.getenv("PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"],
        "secret": os.getenv("PLAID_SECRET") or st.secrets["PLAID_SECRET"],
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["new_access_token"]


def setup_company_integrations():
    """Interactive setup for company integrations"""
    print("🔧 AI CFO - Company Integration Setup")
    print("=" * 40)

    db = DatabaseManager()

    # List companies
    conn = db.get_connection()
    companies = pd.read_sql_query("SELECT * FROM companies", conn)
    conn.close()

    print("Available companies:")
    for _, company in companies.iterrows():
        print(f"  {company['id']}: {company['name']} ({company['industry']})")

    company_id = int(input("\nSelect company ID: "))

    print(f"\nSetting up integrations for company {company_id}...")

    # Setup Plaid
    print("\n1. Plaid Integration:")
    if PLAID_AVAILABLE and (
        os.getenv("PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"]
    ):
        setup_plaid = input("Setup Plaid? (y/n): ").lower() == "y"
        if setup_plaid:
            # In a real app, you'd do the OAuth flow here
            print("🔗 Visit Plaid Link to connect accounts...")
            print("💡 For demo, using mock data instead")
    else:
        print("⚠️ Plaid not configured. Using mock banking data.")

    # Setup QuickBooks
    print("\n2. QuickBooks Integration:")
    if QB_AVAILABLE and (os.getenv("QB_CLIENT_ID") or st.secrets["QB_CLIENT_ID"]):
        setup_qb = input("Setup QuickBooks? (y/n): ").lower() == "y"
        if setup_qb:
            # In a real app, you'd do the OAuth flow here
            print("🔗 Visit QuickBooks OAuth to connect...")
            print("💡 For demo, using mock data instead")
    else:
        print("⚠️ QuickBooks not configured. Using mock accounting data.")

    print(f"\n✅ Setup completed for company {company_id}")


def bulk_sync_all_companies():
    """Sync data for all companies"""
    print("🔄 Bulk syncing all companies...")

    db = DatabaseManager()
    conn = db.get_connection()
    companies = pd.read_sql_query("SELECT id, name FROM companies", conn)
    conn.close()

    for _, company in companies.iterrows():
        company_id = company["id"]
        company_name = company["name"]

        print(f"\n📊 Syncing {company_name} (ID: {company_id})")

        # Sync Plaid
        plaid_success = sync_plaid_data(company_id)

        # Sync QuickBooks
        qb_success = sync_quickbooks_data(company_id)

        if plaid_success or qb_success:
            print(f"✅ {company_name} sync completed")
        else:
            print(f"⚠️ {company_name} sync failed - using mock data")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            setup_company_integrations()
        elif sys.argv[1] == "sync":
            if len(sys.argv) > 2:
                company_id = int(sys.argv[2])
                sync_plaid_data(company_id)
                sync_quickbooks_data(company_id)
            else:
                bulk_sync_all_companies()
        else:
            print("Usage: python data_sync.py [setup|sync] [company_id]")
    else:
        print("AI CFO Data Sync")
        print("Usage:")
        print("  python data_sync.py setup     - Setup company integrations")
        print("  python data_sync.py sync      - Sync all companies")
        print("  python data_sync.py sync 1    - Sync specific company")
