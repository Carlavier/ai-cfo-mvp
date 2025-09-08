# 🔑 API Setup Guide

## Overview

This guide covers setting up all external APIs for the AI CFO MVP:

- **DeepSeek AI** (Required) - For intelligent financial analysis
- **Plaid** (Optional) - For real banking data
- **QuickBooks** (Optional) - For accounting data

## 🤖 DeepSeek AI Setup (Required)

DeepSeek provides cost-effective AI analysis for financial insights.

### Step 1: Create Account

1. Go to [platform.deepseek.com](https://platform.deepseek.com)
2. Click "Sign Up" 
3. Use email or GitHub/Google authentication
4. Verify your email address

### Step 2: Generate API Key

1. Navigate to **API Keys** section
2. Click **"Create API Key"**
3. Name your key (e.g., "AI CFO MVP")
4. Copy the generated key (starts with `sk-`)
5. **⚠️ Important**: Store securely - you can't view it again

### Step 3: Test API Key

```bash
# Test your DeepSeek API key
export DEEPSEEK_API_KEY="sk-your-key-here"
python tests/test_deepseek.py
```

### Pricing

- **Input**: $0.14 per 1M tokens
- **Output**: $0.28 per 1M tokens  
- **Typical financial query**: ~$0.0003
- **Monthly estimate**: $1-10 for MVP usage

### Code Integration

```python
import requests

headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "You are an AI CFO assistant."},
        {"role": "user", "content": "Analyze my cash flow..."}
    ],
    "max_tokens": 500,
    "temperature": 0.3
}

response = requests.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers=headers,
    json=payload
)
```

---

## 🏦 Plaid API Setup (Optional)

Plaid provides access to banking data for real-time financial insights.

### Step 1: Create Developer Account

1. Go to [dashboard.plaid.com/signup](https://dashboard.plaid.com/signup)
2. Choose "Build with Plaid"
3. Fill in company information
4. Verify email and phone

### Step 2: Get Sandbox Credentials

1. In Plaid Dashboard, go to **Team Settings** → **Keys**
2. Copy your credentials:
   - `client_id`
   - `sandbox` secret key
   - Set environment to `sandbox`

### Step 3: Test Sandbox Connection

```python
import plaid
from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient

# Configure Plaid client
configuration = Configuration(
    host=plaid.Environment.sandbox,
    api_key={
        'clientId': 'your_client_id',
        'secret': 'your_sandbox_secret'
    }
)

client = plaid_api.PlaidApi(ApiClient(configuration))
```

### Available Sandbox Banks

For testing, use these sandbox institutions:

| Bank Name | Institution ID | Username | Password |
|-----------|----------------|----------|----------|
| First Platypus Bank | `ins_109508` | `user_good` | `pass_good` |
| First Gingham Credit Union | `ins_109509` | `user_good` | `pass_good` |
| Tartan Bank | `ins_109510` | `user_good` | `pass_good` |

### Data Available

**Account Information**:
- Account names, types, subtypes
- Current and available balances
- Account and routing numbers (masked)

**Transactions**:
- Transaction amounts and dates
- Merchant names and categories
- Pending status
- Location data (when available)

**Identity** (with user consent):
- Account holder names and addresses
- Phone numbers and emails

### Pricing

- **Sandbox**: Free unlimited usage
- **Development**: First 100 Items free
- **Production**: $0.50-2.00 per connected account/month

### Code Example

```python
# Create Link Token
from plaid.model.link_token_create_request import LinkTokenCreateRequest

request = LinkTokenCreateRequest(
    products=[plaid.Products('transactions')],
    client_name="AI CFO App",
    country_codes=[plaid.CountryCode('US')],
    language='en',
    user={'client_user_id': 'unique_user_id'}
)

response = client.link_token_create(request)
link_token = response['link_token']

# Get Accounts
from plaid.model.accounts_get_request import AccountsGetRequest

accounts_request = AccountsGetRequest(access_token=access_token)
accounts_response = client.accounts_get(accounts_request)
accounts = accounts_response['accounts']

# Get Transactions
from plaid.model.transactions_get_request import TransactionsGetRequest

transactions_request = TransactionsGetRequest(
    access_token=access_token,
    start_date=datetime(2023, 1, 1).date(),
    end_date=datetime.now().date()
)

transactions_response = client.transactions_get(transactions_request)
transactions = transactions_response['transactions']
```

---

## 📊 QuickBooks API Setup (Optional)

QuickBooks provides comprehensive accounting data.

### Step 1: Create Developer Account

1. Go to [developer.intuit.com](https://developer.intuit.com)
2. Click **"Get started for free"**
3. Sign in with existing Intuit account or create new
4. Complete developer profile

### Step 2: Create App

1. Go to **"My Apps"** → **"Create an app"**
2. Select **"QuickBooks Online Accounting API"**
3. Fill in app details:
   - App name: "AI CFO MVP"
   - Description: "Financial intelligence platform"
4. Get your app credentials:
   - Client ID
   - Client Secret

### Step 3: Configure OAuth

**Redirect URIs** (for local development):
```
http://localhost:8501/callback
http://localhost:3000/callback
```

**Scopes needed**:
- `com.intuit.quickbooks.accounting`

### Step 4: Sandbox Company

QuickBooks automatically creates a sandbox company with sample data:

- Sample customers, vendors, items
- Historical transactions
- Chart of accounts
- Financial reports

### Available Data

**Company Information**:
- Company name, address, phone
- Tax ID, legal name
- Fiscal year settings

**Chart of Accounts**:
- Account names, numbers, types
- Current balances
- Active/inactive status

**Customers & Invoices**:
- Customer information
- Invoice details, line items
- Payment status, due dates
- Aging reports

**Vendors & Bills**:
- Vendor information  
- Bill details, due dates
- Payment status
- 1099 information

**Items & Inventory**:
- Service and product items
- Inventory tracking
- Cost and pricing

**Financial Reports**:
- Profit & Loss statements
- Balance Sheet
- Cash Flow Statement
- Trial Balance
- Custom date ranges

### Pricing

- **Sandbox**: Free unlimited usage
- **Production**: Free up to certain limits, then usage-based pricing

### Code Example

```python
from intuitlib.client import AuthClient
from quickbooks import QuickBooks

# OAuth Setup  
auth_client = AuthClient(
    client_id='your_client_id',
    client_secret='your_client_secret',
    environment='sandbox',
    redirect_uri='http://localhost:8501/callback'
)

# Get authorization URL
auth_url = auth_client.get_authorization_url([Scopes.ACCOUNTING])

# After user authorizes, exchange code for tokens
auth_client.get_bearer_token(auth_code)

# Create QuickBooks client
qb_client = QuickBooks(
    sandbox=True,
    consumer_key=client_id,
    consumer_secret=client_secret,
    access_token=auth_client.access_token,
    access_token_secret='',
    company_id=auth_client.realm_id
)

# Get company info
from quickbooks.objects import CompanyInfo
company = CompanyInfo.all(qb=qb_client)[0]

# Get invoices
from quickbooks.objects import Invoice
invoices = Invoice.all(qb=qb_client)

# Get profit & loss report
url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{company_id}/reports/ProfitAndLoss"
headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}
params = {'start_date': '2023-01-01', 'end_date': '2023-12-31'}
response = requests.get(url, headers=headers, params=params)
```

---

## 🔄 Integration Testing

### Test Script

Create `tests/test_apis.py`:

```python
import os
import requests
from datetime import datetime

def test_deepseek():
    """Test DeepSeek API connection"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not found")
        return False
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": "Test connection"}],
        "max_tokens": 50
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, json=payload, timeout=30
        )
        
        if response.status_code == 200:
            print("✅ DeepSeek API connection successful")
            return True
        else:
            print(f"❌ DeepSeek API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ DeepSeek API error: {e}")
        return False

def test_plaid():
    """Test Plaid API connection"""
    client_id = os.getenv('PLAID_CLIENT_ID')
    secret = os.getenv('PLAID_SECRET')
    
    if not client_id or not secret:
        print("❌ Plaid credentials not found")
        return False
    
    # Test with sandbox
    try:
        import plaid
        from plaid.api import plaid_api
        from plaid.configuration import Configuration
        from plaid.api_client import ApiClient
        
        configuration = Configuration(
            host=plaid.Environment.sandbox,
            api_key={'clientId': client_id, 'secret': secret}
        )
        
        client = plaid_api.PlaidApi(ApiClient(configuration))
        print("✅ Plaid API connection successful")
        return True
    except Exception as e:
        print(f"❌ Plaid API error: {e}")
        return False

def test_quickbooks():
    """Test QuickBooks API connection"""
    client_id = os.getenv('QB_CLIENT_ID')
    secret = os.getenv('QB_CLIENT_SECRET')
    
    if not client_id or not secret:
        print("❌ QuickBooks credentials not found")
        return False
    
    try:
        from intuitlib.client import AuthClient
        
        auth_client = AuthClient(
            client_id=client_id,
            client_secret=secret,
            environment='sandbox'
        )
        print("✅ QuickBooks API setup successful")
        return True
    except Exception as e:
        print(f"❌ QuickBooks API error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing API Connections...")
    print("-" * 40)
    
    results = {
        "DeepSeek": test_deepseek(),
        "Plaid": test_plaid(),
        "QuickBooks": test_quickbooks()
    }
    
    print("\n📊 Test Results:")
    for api, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {api}")
    
    working_apis = sum(results.values())
    print(f"\n🎯 {working_apis}/3 APIs working")
    
    if working_apis == 0:
        print("⚠️  No APIs configured - app will use mock data only")
    elif working_apis < 3:
        print("💡 Some APIs missing - app will use mix of real and mock data")
    else:
        print("🚀 All APIs ready - full functionality available!")
```

### Run Tests

```bash
# Set your API keys
export DEEPSEEK_API_KEY="your-key"
export PLAID_CLIENT_ID="your-id"
export PLAID_SECRET="your-secret"
export QB_CLIENT_ID="your-id"
export QB_CLIENT_SECRET="your-secret"

# Run tests
python tests/test_apis.py
```

---

## 🔒 Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
2. **Use environment variables or secure vaults**
3. **Rotate keys regularly**
4. **Use different keys for dev/staging/production**

### .env File Structure

```bash
# .env (never commit this file)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
PLAID_CLIENT_ID=abcdefghijklmnop1234567890
PLAID_SECRET=fedcba0987654321abcdefghijklmnop
QB_CLIENT_ID=ABCDefgh12345678ijklmnopqrstuvwx
QB_CLIENT_SECRET=zyxwvutsrq9876543210ABCDEFGHIJK
```

### .gitignore Entries

```gitignore
# Environment variables
.env
.env.local
.env.production

# API credentials
config/secrets.json
credentials.json

# Database
*.db
*.sqlite

# Logs
*.log
logs/
```

---

## 📈 Rate Limits & Quotas

### DeepSeek AI

- **Rate limit**: 60 requests per minute
- **Token limit**: 8192 tokens per request
- **Daily quota**: No hard limit (pay-as-you-go)

### Plaid

- **Sandbox**: Unlimited
- **Development**: 100 items free, then $0.50-2.00/item/month
- **Rate limit**: 600 requests per minute per client_id

### QuickBooks

- **Sandbox**: Unlimited
- **Production**: 500 requests per minute per app
- **Daily quota**: No hard limit

### Handling Rate Limits

```python
import time
import random

def api_call_with_retry(api_function, max_retries=3):
    """Generic retry logic for API calls"""
    for attempt in range(max_retries):
        try:
            return api_function()
        except Exception as e:
            if "rate limit" in str(e).lower():
                wait_time = (2 ** attempt) + random.random()
                print(f"Rate limited. Waiting {wait_time:.2f}s...")
                time.sleep(wait_time)
            else:
                raise e
    
    raise Exception(f"Failed after {max_retries} attempts")

# Usage
result = api_call_with_retry(lambda: deepseek_api_call())
```

---

## 🚀 Production Considerations

### Environment Variables

For production deployment, ensure these are properly set:

```bash
# Required
DEEPSEEK_API_KEY=sk-production-key

# Optional but recommended
PLAID_CLIENT_ID=prod_client_id
PLAID_SECRET=prod_secret
PLAID_ENV=production

QB_CLIENT_ID=prod_client_id
QB_CLIENT_SECRET=prod_secret

# Security
JWT_SECRET=your-jwt-secret
API_RATE_LIMIT=100  # requests per minute per user
```

### Monitoring

Add API monitoring:

```python
import time
from functools import wraps

def monitor_api_calls(api_name):
    """Decorator to monitor API performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                result = None
                success = False
                raise
            finally:
                duration = time.time() - start_time
                log_api_call(api_name, duration, success)
            return result
        return wrapper
    return decorator

@monitor_api_calls("deepseek")
def call_deepseek_api():
    # API call implementation
    pass
```

### Cost Monitoring

```python
def track_api_costs():
    """Track API usage costs"""
    daily_usage = {
        "deepseek": {"calls": 0, "tokens": 0, "cost": 0.0},
        "plaid": {"calls": 0, "items": 0, "cost": 0.0},
        "quickbooks": {"calls": 0, "cost": 0.0}
    }
    
    # Update costs after each API call
    return daily_usage
```

---

**Need help with API setup? Check our [troubleshooting guide](troubleshooting.md) or [open an issue](https://github.com/yourusername/ai-cfo-mvp/issues).**