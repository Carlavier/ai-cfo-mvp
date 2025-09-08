# data_sync.py - API Data Sync Script
import os
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from database_module import DatabaseManager
from dotenv import load_dotenv

load_dotenv()

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
        
        client_id = os.getenv('PLAID_CLIENT_ID')
        secret = os.getenv('PLAID_SECRET')
        env = os.getenv('PLAID_ENV', 'sandbox').capitalize()

        if not client_id or not secret:
            print("⚠️ Plaid credentials not found. Set PLAID_CLIENT_ID and PLAID_SECRET")
            self.plaid_client = None
            return
        
        try:
            configuration = Configuration(
                host=getattr(plaid.Environment, env),
                api_key={'clientId': client_id, 'secret': secret}
            )
            api_client = ApiClient(configuration)
            self.plaid_client = plaid_api.PlaidApi(api_client)
            print("✅ Plaid client initialized")
        except Exception as e:
            print(f"❌ Plaid setup failed: {e}")
            self.plaid_client = None
    
    def setup_quickbooks(self):
        """Setup QuickBooks client"""
        if not QB_AVAILABLE:
            print("⚠️ QuickBooks not available. Install: pip install quickbooks-python3 intuitlib")
            self.qb_client = None
            return
        
        client_id = os.getenv('QB_CLIENT_ID')
        secret = os.getenv('QB_CLIENT_SECRET')
        
        if not client_id or not secret:
            print("⚠️ QuickBooks credentials not found. Set QB_CLIENT_ID and QB_CLIENT_SECRET")
            self.qb_client = None
            return
        
        try:
            self.auth_client = AuthClient(
                client_id=client_id,
                client_secret=secret,
                environment='sandbox',
                redirect_uri='http://localhost:8501/callback'
            )
            print("✅ QuickBooks client initialized")
        except Exception as e:
            print(f"❌ QuickBooks setup failed: {e}")
            self.qb_client = None

def sync_plaid_data(company_id: int):
    """Sync Plaid banking data for a company"""
    sync_manager = DataSyncManager()
    
    if not sync_manager.plaid_client:
        print("❌ Plaid client not available")
        return False
    
    try:
        # Get stored access token for company
        access_token = get_company_plaid_token(company_id)
        
        if not access_token:
            print(f"❌ No Plaid access token found for company {company_id}")
            return False
        
        print(f"🔄 Syncing Plaid data for company {company_id}...")
        
        # Sync accounts
        accounts_synced = sync_plaid_accounts(sync_manager, company_id, access_token)
        
        # Sync transactions
        transactions_synced = sync_plaid_transactions(sync_manager, company_id, access_token)
        
        # Log sync
        sync_manager.db.log_sync(
            company_id, 'plaid', 'full_sync', 
            accounts_synced + transactions_synced, True
        )
        
        print(f"✅ Plaid sync completed: {accounts_synced} accounts, {transactions_synced} transactions")
        return True
        
    except Exception as e:
        print(f"❌ Plaid sync failed: {e}")
        sync_manager.db.log_sync(
            company_id, 'plaid', 'full_sync', 0, False, str(e)
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
        local_account = sync_manager.db.get_account_by_plaid_id(company_id, plaid_account_id)
        
        if not local_account:
            continue
        
        transaction_data = {
            'account_id': local_account['id'],
            'transaction_id': transaction['transaction_id'],
            'amount': -transaction['amount'],  # Plaid uses positive for outflow
            'date': transaction['date'].isoformat(),
            'merchant_name': transaction.get('merchant_name', 'Unknown'),
            'category': ','.join(transaction['category']) if transaction['category'] else '',
            'pending': transaction['pending']
        }
        
        if sync_manager.db.save_transaction(transaction_data) > 0:
            transactions_synced += 1
    
    return transactions_synced

def sync_quickbooks_data(company_id: int):
    """Sync QuickBooks accounting data for a company"""
    sync_manager = DataSyncManager()
    
    if not sync_manager.auth_client:
        print("❌ QuickBooks client not available")
        return False
    
    try:
        # Get stored QB tokens for company
        qb_tokens = get_company_qb_tokens(company_id)
        
        if not qb_tokens:
            print(f"❌ No QuickBooks tokens found for company {company_id}")
            return False
        
        print(f"🔄 Syncing QuickBooks data for company {company_id}...")
        
        # Create QB client
        qb_client = QuickBooks(
            sandbox=True,
            consumer_key=os.getenv('QB_CLIENT_ID'),
            consumer_secret=os.getenv('QB_CLIENT_SECRET'),
            access_token=qb_tokens['access_token'],
            access_token_secret='',
            company_id=qb_tokens['realm_id']
        )
        
        # Sync invoices
        invoices_synced = sync_qb_invoices(sync_manager, company_id, qb_client)
        
        # Sync bills
        bills_synced = sync_qb_bills(sync_manager, company_id, qb_client)
        
        # Log sync
        sync_manager.db.log_sync(
            company_id, 'quickbooks', 'full_sync',
            invoices_synced + bills_synced, True
        )
        
        print(f"✅ QuickBooks sync completed: {invoices_synced} invoices, {bills_synced} bills")
        return True
        
    except Exception as e:
        print(f"❌ QuickBooks sync failed: {e}")
        sync_manager.db.log_sync(
            company_id, 'quickbooks', 'full_sync', 0, False, str(e)
        )
        return False

def sync_qb_invoices(sync_manager, company_id: int, qb_client) -> int:
    """Sync QuickBooks invoices"""
    invoices = Invoice.all(qb=qb_client)
    invoices_synced = 0
    
    for invoice in invoices:
        # Calculate days overdue
        if invoice.DueDate:
            due_date = datetime.strptime(invoice.DueDate, '%Y-%m-%d')
            days_overdue = max(0, (datetime.now() - due_date).days) if invoice.Balance > 0 else 0
        else:
            days_overdue = 0
        
        # Determine status
        if invoice.Balance == 0:
            status = 'paid'
        elif days_overdue > 0:
            status = 'overdue'
        else:
            status = 'pending'
        
        invoice_data = {
            'company_id': company_id,
            'qb_invoice_id': invoice.Id,
            'invoice_number': invoice.DocNumber or f"INV-{invoice.Id}",
            'customer_name': invoice.CustomerRef.name if invoice.CustomerRef else 'Unknown',
            'amount': float(invoice.TotalAmt or 0),
            'balance': float(invoice.Balance or 0),
            'due_date': invoice.DueDate or datetime.now().strftime('%Y-%m-%d'),
            'issue_date': invoice.TxnDate or datetime.now().strftime('%Y-%m-%d'),
            'status': status,
            'days_overdue': days_overdue
        }
        
        sync_manager.db.save_invoice(invoice_data)
        invoices_synced += 1
    
    return invoices_synced

def sync_qb_bills(sync_manager, company_id: int, qb_client) -> int:
    """Sync QuickBooks bills"""
    bills = Bill.all(qb=qb_client)
    bills_synced = 0
    
    for bill in bills:
        # Determine status
        if bill.Balance == 0:
            status = 'paid'
        elif bill.DueDate:
            due_date = datetime.strptime(bill.DueDate, '%Y-%m-%d')
            if due_date < datetime.now():
                status = 'overdue'
            else:
                status = 'pending'
        else:
            status = 'pending'
        
        bill_data = {
            'company_id': company_id,
            'qb_bill_id': bill.Id,
            'bill_number': bill.DocNumber or f"BILL-{bill.Id}",
            'vendor_name': bill.VendorRef.name if bill.VendorRef else 'Unknown',
            'amount': float(bill.TotalAmt or 0),
            'balance': float(bill.Balance or 0),
            'due_date': bill.DueDate or datetime.now().strftime('%Y-%m-%d'),
            'category': 'General',
            'status': status
        }
        
        sync_manager.db.save_bill(bill_data)
        bills_synced += 1
    
    return bills_synced

# def get_company_plaid_token(company_id: int) -> str:
#     """Get stored Plaid access token for company"""
#     # In a real app, you'd store these in the database
#     # For demo, return None (will use mock data)
#     return None

# def get_company_qb_tokens(company_id: int) -> Dict:
#     """Get stored Plaid access token for company"""
#     # In a real app, you'd store these in the database
#     # For demo, return None (will use mock data)
#     return None

def get_company_public_token(company_id: int) -> str:
    """Demo: Return a mock Plaid public_token for the given company_id.
    Prefer stored DB value (if Link flow was used); otherwise return demo token."""
    # Try DB first
    db = DatabaseManager()
    rec = db.get_plaid_token_record(company_id)
    if rec and rec.get('public_token'):
        return rec.get('public_token')
    
    # Demo/testing fallback tokens
    demo_tokens = {
        1: "public-sandbox-token-1",
        2: "public-sandbox-token-2",
        3: "public-sandbox-token-3"
    }
    return demo_tokens.get(company_id)

def create_link_token(company_id: int) -> str:
    """Create a Plaid link token for frontend Link initialization (requires PLAID_AVAILABLE)."""
    if not PLAID_AVAILABLE:
        print("⚠️ Plaid SDK not installed, cannot create link token.")
        return None
    try:
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
        # use environment from .env
        client_id = os.getenv('PLAID_CLIENT_ID')
        secret = os.getenv('PLAID_SECRET')
        env = os.getenv('PLAID_ENV', 'sandbox').capitalize()
        configuration = Configuration(
            host=getattr(plaid.Environment, env),
            api_key={'clientId': client_id, 'secret': secret}
        )
        api_client = ApiClient(configuration)
        client = plaid_api.PlaidApi(api_client)
        request = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=str(company_id)),
            client_name="AI CFO Demo",
            products=["transactions", "auth"],
            country_codes=["US"],
            language="en"
        )
        response = client.link_token_create(request)
        # response has attribute link_token
        link_token = getattr(response, 'link_token', None) or response['link_token']
        return link_token
    except Exception as e:
        print(f"❌ Link token creation failed: {e}")
        return None

def exchange_public_token(public_token: str, company_id: int) -> str:
    """Exchange a Plaid public_token for an access_token and persist it in DB.
    Returns the access_token or None on failure."""
    if not PLAID_AVAILABLE:
        print("⚠️ Plaid SDK not installed, cannot exchange public token.")
        return None
    try:
        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
        client_id = os.getenv('PLAID_CLIENT_ID')
        secret = os.getenv('PLAID_SECRET')
        env = os.getenv('PLAID_ENV', 'sandbox').capitalize()
        configuration = Configuration(
            host=getattr(plaid.Environment, env),
            api_key={'clientId': client_id, 'secret': secret}
        )
        api_client = ApiClient(configuration)
        client = plaid_api.PlaidApi(api_client)
        request = ItemPublicTokenExchangeRequest(public_token=public_token)
        response = client.item_public_token_exchange(request)
        access_token = getattr(response, 'access_token', None) or response['access_token']
        item_id = getattr(response, 'item_id', None) or response.get('item_id')
        # persist to DB
        db = DatabaseManager()
        db.save_plaid_token(company_id, public_token=public_token, access_token=access_token, item_id=item_id)
        return access_token
    except Exception as e:
        print(f"❌ Plaid token exchange failed: {e}")
        return None

def get_company_plaid_token(company_id: int) -> str:
    """Return a valid Plaid access_token for company.
    Flow:
      1) Try DB stored access_token
      2) If missing and a public_token exists (DB/demo), try exchange_public_token()
      3) Fallback to deterministic demo mock token when Plaid SDK not used
    """
    db = DatabaseManager()
    rec = db.get_plaid_token_record(company_id)
    if rec and rec.get('access_token'):
        return rec.get('access_token')
    # If public_token exists (DB or demo), try exchanging with Plaid to get real access_token
    public_token = get_company_public_token(company_id)
    if public_token and PLAID_AVAILABLE:
        access_token = exchange_public_token(public_token, company_id)
        if access_token:
            return access_token
    # Fallback demo deterministic token (not valid with real Plaid, only for app demo paths)
    import uuid, hashlib
    identifier = hashlib.sha256(public_token.encode() if public_token else f"demo-{company_id}".encode()).hexdigest()[:24]
    return f"access-sandbox-{identifier}"

def get_company_qb_tokens(company_id: int) -> Dict:
    """Get stored QuickBooks tokens for company (demo mock)"""
    # In a real app, you'd fetch these from the database and handle refresh tokens.
    # Demo values below let the QuickBooks sync path run without real OAuth.
    return {
        "access_token": f"mock-qb-access-token-{company_id}",
        "refresh_token": f"mock-qb-refresh-token-{company_id}",
        "realm_id": str(1000 + company_id),      # demo company realm id
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat()
    }

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
    if PLAID_AVAILABLE and os.getenv('PLAID_CLIENT_ID'):
        setup_plaid = input("Setup Plaid? (y/n): ").lower() == 'y'
        if setup_plaid:
            # In a real app, you'd do the OAuth flow here
            print("🔗 Visit Plaid Link to connect accounts...")
            print("💡 For demo, using mock data instead")
    else:
        print("⚠️ Plaid not configured. Using mock banking data.")
    
    # Setup QuickBooks
    print("\n2. QuickBooks Integration:")
    if QB_AVAILABLE and os.getenv('QB_CLIENT_ID'):
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