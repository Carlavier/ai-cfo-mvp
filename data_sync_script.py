# data_sync.py - API Data Sync Script
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict
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

        client_id = os.getenv(
            "PLAID_CLIENT_ID") or st.secrets["PLAID_CLIENT_ID"]
        secret = os.getenv("PLAID_SECRET") or st.secrets["PLAID_SECRET"]
        # Normalize env and map to correct constants
        env_name = os.getenv("PLAID_ENV", "sandbox").capitalize() or str(
            st.secrets["PLAID_ENV"] or "sandbox").capitalize()

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
                "⚠️ QuickBooks not available. Install: pip install quickbooks-python3 intuitlib")
            self.qb_client = None
            return

        client_id = os.getenv("QB_CLIENT_ID") or st.secrets["QB_CLIENT_ID"]
        secret = os.getenv(
            "QB_CLIENT_SECRET") or st.secrets["QB_CLIENT_SECRET"]
        base_url = os.getenv("APP_BASE_URL") or st.secrets["APP_BASE_URL"]
        qb_redirect_uri = os.getenv(
            "QB_CLIENT_REDIRECT_URL") or st.secrets["QB_CLIENT_REDIRECT_URL"]

        if not qb_redirect_uri:
            base = (base_url or "http://localhost:8501").rstrip("/")
            qb_redirect_uri = os.getenv(
                "APP_REDIRECT_URI", f"{base}/") or st.secrets.get("APP_REDIRECT_URI", f"{base}/")

        if not client_id or not secret:
            print(
                "⚠️ QuickBooks credentials not found. Set QB_CLIENT_ID and QB_CLIENT_SECRET")
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
            company_id, 'plaid', 'mock_seed', acc_count + tx_count, True)
        print(
            f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions")
        return True

    try:
        # Get stored access token for company
        access_token = get_company_plaid_token(company_id)

        if not access_token:
            print(
                f"❌ No Plaid access token found for company {company_id} — using mock data")
            acc_count, tx_count = seed_mock_plaid(sync_manager.db, company_id)
            sync_manager.db.log_sync(
                company_id, 'plaid', 'mock_seed', acc_count + tx_count, True)
            print(
                f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions")
            return True

        print(f"🔄 Syncing Plaid data for company {company_id}...")

        # Sync accounts
        accounts_synced = sync_plaid_accounts(
            sync_manager, company_id, access_token)

        # Sync transactions
        transactions_synced = sync_plaid_transactions(
            sync_manager, company_id, access_token)

        # Log sync
        sync_manager.db.log_sync(
            company_id, 'plaid', 'full_sync',
            accounts_synced + transactions_synced, True
        )

        print(
            f"✅ Plaid sync completed: {accounts_synced} accounts, {transactions_synced} transactions")
        return True

    except Exception as e:
        print(f"❌ Plaid sync failed: {e} — falling back to mock data")
        try:
            acc_count, tx_count = seed_mock_plaid(sync_manager.db, company_id)
            sync_manager.db.log_sync(
                company_id, 'plaid', 'mock_seed', acc_count + tx_count, True)
            print(
                f"✅ Mock Plaid data seeded: {acc_count} accounts, {tx_count} transactions")
            return True
        except Exception as inner:
            print(f"❌ Mock Plaid seeding failed: {inner}")
            sync_manager.db.log_sync(
                company_id, 'plaid', 'full_sync', 0, False, f"api_error={e}; mock_error={inner}"
            )
            return False


def sync_plaid_accounts(sync_manager, company_id: int, access_token: str) -> int:
    """Sync Plaid accounts"""
    request = AccountsGetRequest(access_token=access_token)
    response = sync_manager.plaid_client.accounts_get(request)

    accounts_synced = 0

    for account in response['accounts']:
        account_data = {
            'company_id': company_id,
            'account_id': account['account_id'],
            'name': account['name'],
            'institution_name': account.get('institution_name', ''),
            'type': account['type'],
            'subtype': account['subtype'],
            'current_balance': account['balances']['current'],
            'available_balance': account['balances']['available'],
            'mask': account.get('mask', '')
        }

        sync_manager.db.save_account(account_data)
        accounts_synced += 1

    return accounts_synced


def sync_plaid_transactions(sync_manager, company_id: int, access_token: str) -> int:
    """Sync Plaid transactions"""
    # Get transactions for last 30 days
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    request = TransactionsGetRequest(
        access_token=access_token,
        start_date=start_date.date(),
        end_date=end_date.date()
    )

    response = sync_manager.plaid_client.transactions_get(request)
    transactions_synced = 0

    for transaction in response['transactions']:
        # Get local account ID
        plaid_account_id = transaction['account_id']
        local_account = sync_manager.db.get_account_by_plaid_id(
            company_id, plaid_account_id)

        if not local_account:
            continue

        transaction_data = {
            'account_id': local_account['id'],
            'transaction_id': transaction['transaction_id'],
            # Plaid uses positive for outflow
            'amount': -transaction['amount'],
            'date': transaction['date'].isoformat(),
            'merchant_name': transaction.get('merchant_name', 'Unknown'),
            'category': ','.join(transaction['category']) if transaction['category'] else '',
            'pending': transaction['pending']
        }

        if sync_manager.db.save_transaction(transaction_data) > 0:
            transactions_synced += 1

    return transactions_synced


def fetch_qb_data(endpoint: str, qb_tokens: Dict):
    """Gọi QuickBooks API trả về JSON"""
    base_url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{qb_tokens['realm_id']}"
    url = f"{base_url}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {qb_tokens['access_token']}",
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        raise Exception(f"QuickBooks API error {resp.status_code}: {resp.text}")

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
            "days_overdue": 0
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
            "status": bill.get("TxnStatus", "pending")
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
        sync_manager.db.log_sync(company_id, "quickbooks", "mock_seed", inv + bill, True)
        return True

    try:
        print(f"🔄 Sync QuickBooks data for company {company_id}...")

        invoices_synced = sync_qb_invoices(sync_manager, company_id, qb_tokens)
        bills_synced = sync_qb_bills(sync_manager, company_id, qb_tokens)

        sync_manager.db.log_sync(
            company_id, "quickbooks", "full_sync",
            invoices_synced + bills_synced, True
        )

        print(f"✅ Synced: {invoices_synced} invoices, {bills_synced} bills")
        return True
    except Exception as e:
        print(f"❌ Sync failed: {e}, falling back to mock")
        inv, bill = seed_mock_quickbooks(sync_manager.db, company_id)
        sync_manager.db.log_sync(company_id, "quickbooks", "mock_seed", inv + bill, True)
        return True


def get_company_plaid_token(company_id: int) -> str:
    """Get stored Plaid access token for company"""
    # In a real app, you'd store these in the database
    # For demo, return None (will use mock data)
    return None


def get_company_qb_tokens(company_id: int) -> Dict:
    if st.session_state["access_token"] and st.session_state["refresh_token"] and st.session_state["realm_id"]:
        return {
            'access_token': st.session_state["access_token"],
            'refresh_token': st.session_state["refresh_token"],
            'realm_id': st.session_state["realm_id"]
        }

    # Nếu chưa có code thì chỉ hiển thị nút Connect
    CLIENT_ID = os.getenv("QB_CLIENT_ID") or st.secrets["QB_CLIENT_ID"]
    REDIRECT_URI = os.getenv(
        "QB_CLIENT_REDIRECT_URL") or st.secrets["QB_CLIENT_REDIRECT_URL"]
    SCOPES = "com.intuit.quickbooks.accounting com.intuit.quickbooks.payment"
    STATE = "12345"

    auth_url = (
        "https://appcenter.intuit.com/connect/oauth2?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "scope": SCOPES,
            "redirect_uri": REDIRECT_URI,
            "state": STATE,
        })
    )

    st.markdown(f"[🔗 Connect to QuickBooks]({auth_url})")

    return None


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
    if PLAID_AVAILABLE and (os.getenv('PLAID_CLIENT_ID') or st.secrets.get("PLAID_CLIENT_ID")):
        setup_plaid = input("Setup Plaid? (y/n): ").lower() == 'y'
        if setup_plaid:
            # In a real app, you'd do the OAuth flow here
            print("🔗 Visit Plaid Link to connect accounts...")
            print("💡 For demo, using mock data instead")
    else:
        print("⚠️ Plaid not configured. Using mock banking data.")

    # Setup QuickBooks
    print("\n2. QuickBooks Integration:")
    if QB_AVAILABLE and (os.getenv('QB_CLIENT_ID') or st.secrets.get("QB_CLIENT_ID")):
        setup_qb = input("Setup QuickBooks? (y/n): ").lower() == 'y'
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
        company_id = company['id']
        company_name = company['name']

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
