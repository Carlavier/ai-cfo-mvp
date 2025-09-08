# 🚀 Quick Start Guide - AI CFO MVP

*Get your AI CFO system running in 5 minutes!*

## 📋 Prerequisites

- Python 3.9+
- Git
- Internet connection

## ⚡ 5-Minute Setup

### 1. Clone & Install (2 minutes)

```bash
# Clone repository
git clone https://github.com/yourusername/ai-cfo-mvp.git
cd ai-cfo-mvp

# Install dependencies
pip install streamlit plotly pandas requests python-dotenv

# Or use requirements file
pip install -r requirements.txt
```

### 2. Get DeepSeek API Key (2 minutes)

1. **Sign up**: Go to [platform.deepseek.com](https://platform.deepseek.com) 
2. **Create API Key**: Dashboard → API Keys → Create New
3. **Copy Key**: Starts with `sk-...`

### 3. Set Environment Variable (30 seconds)

```bash
# Linux/Mac
export DEEPSEEK_API_KEY="sk-your-key-here"

# Windows
set DEEPSEEK_API_KEY=sk-your-key-here

# Or create .env file
echo "DEEPSEEK_API_KEY=sk-your-key-here" > .env
```

### 4. Run the App (30 seconds)

```bash
streamlit run ai_cfo_with_db.py
```

**🎉 That's it! Your app is running at http://localhost:8501**

---

## 🔐 Demo Login

Use these accounts to explore different user roles:

| Role | Username | Password | What You Can Do |
|------|----------|----------|----------------|
| **CEO** | `ceo` | `ceo123` | • View executive dashboard<br>• See all financial metrics<br>• Access AI insights<br>• Full system access |
| **CFO** | `cfo` | `cfo123` | • Detailed cash flow analysis<br>• Manage AR/AP<br>• Financial planning<br>• AI financial advisor |
| **Accountant** | `accountant` | `acc123` | • Transaction management<br>• Invoice/bill processing<br>• Data categorization<br>• Reconciliation |
| **Manager** | `manager` | `mgr123` | • Department expenses<br>• Submit requests<br>• Team budgets<br>• Limited AI access |
| **Employee** | `employee` | `emp123` | • Submit expense reports<br>• View own transactions<br>• Check reimbursements |

---

## 🎯 What to Try First

### As CEO:
1. **Login** with `ceo/ceo123`
2. **Check Dashboard** - See key metrics like cash runway (127 days)
3. **Ask AI CFO**: "What are my biggest financial risks?"
4. **Review Alerts** - See AI-generated insights

### As CFO:
1. **Switch to CFO role** (`cfo/cfo123`)
2. **Go to Cash Flow** - View 13-week forecast
3. **Check AR Management** - See overdue invoices ($23,400)
4. **Use AI Chat** - Ask "How can I improve cash flow?"

### Test AI Features:
1. **Click "AI Chat"** in sidebar
2. **Try these questions**:
   - "What's my cash runway?"
   - "Should I be worried about overdue invoices?"
   - "How can I reduce expenses?"
   - "What's my biggest financial risk?"

---

## 📊 Sample Data Overview

Your MVP comes with realistic demo data:

### 💰 Financial Snapshot:
- **Current Cash**: $47,332
- **Outstanding AR**: $23,400 (3 overdue invoices)
- **Upcoming AP**: $15,600 (5 pending bills)
- **Monthly Burn**: $28,500
- **Cash Runway**: 127 days

### 🏦 Bank Accounts:
- Business Checking: $47,332
- Business Savings: $125,000  
- Credit Line: -$8,500 (used)

### 📄 Invoices:
- ABC Corporation: $8,500 (45 days overdue)
- Enterprise LLC: $25,000 (30 days overdue)
- XYZ Tech: $12,000 (current)

### 💳 Recent Transactions:
- AWS Services: -$2,500
- Stripe Payment: +$15,000
- Google Ads: -$3,200
- Office Depot: -$1,200

---

## 🤖 AI Features to Explore

### 1. Smart Cash Flow Analysis
- **Ask**: "Analyze my cash runway"
- **Get**: Detailed breakdown with recommendations

### 2. AR Collection Insights
- **Ask**: "What should I do about overdue invoices?"
- **Get**: Prioritized action plan

### 3. Expense Optimization
- **Ask**: "How can I reduce monthly expenses?"
- **Get**: Specific cost-cutting suggestions

### 4. Financial Health Check
- **Ask**: "Is my company financially healthy?"
- **Get**: Comprehensive assessment with metrics

---

## 🚀 Deploy in 5 Minutes (Optional)

Want to share with others? Deploy to Streamlit Cloud for **FREE**:

### Step 1: Push to GitHub
```bash
git init
git add .
git commit -m "AI CFO MVP"
git push origin main
```

### Step 2: Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click "New app"
3. Connect your GitHub repo
4. Set main file: `ai_cfo_with_db.py`
5. Add secret: `DEEPSEEK_API_KEY = "your-key"`
6. Click "Deploy"

**🎉 Your app is now live and shareable!**

---

## 🎨 Customization Ideas

### Change Company Data:
Edit the sample data in the `insert_default_data()` function:

```python
# Change company name
cursor.execute('''
    INSERT INTO companies (name, industry) 
    VALUES ('Your Company Name', 'Your Industry')
''')

# Modify cash balances
accounts_data = [
    (company_id, 'acc_001', 'Your Bank - Checking', 'depository', 'checking', 75000.00, 72000.00),
    # Add your actual accounts
]
```

### Add Your Logo:
```python
# Add to the top of your Streamlit app
st.image("your-logo.png", width=200)
st.title("Your Company AI CFO")
```

### Custom AI Personality:
Modify the system prompt in `DeepSeekClient`:

```python
system_prompt = """You are the AI CFO for [Your Company]. 
You have a [personality trait] personality and always focus on [your priorities].
Industry context: [your industry details]"""
```

---

## 🛠️ Troubleshooting

### App Won't Start?
```bash
# Check Python version (need 3.9+)
python --version

# Reinstall dependencies
pip install --upgrade streamlit plotly pandas requests

# Check for port conflicts
streamlit run ai_cfo_with_db.py --server.port 8502
```

### AI Not Working?
```bash
# Test your API key
python -c "
import requests
headers = {'Authorization': 'Bearer YOUR_KEY'}
r = requests.post('https://api.deepseek.com/v1/chat/completions', 
    headers=headers, json={'model': 'deepseek-chat', 'messages': [{'role': 'user', 'content': 'test'}]})
print(r.status_code)
"
```

### Database Issues?
```bash
# Delete and recreate database
rm ai_cfo.db
streamlit run ai_cfo_with_db.py  # Will recreate with fresh data
```

### Performance Slow?
```bash
# Clear Streamlit cache
streamlit cache clear

# Restart app
pkill -f streamlit
streamlit run ai_cfo_with_db.py
```

---

## 📚 Next Steps

### Learn More:
- 📖 [Full Documentation](README.md)
- 🔑 [API Setup Guide](docs/api-setup.md)
- 🚀 [Deployment Guide](docs/deployment.md)

### Add Real Data:
- 🏦 [Connect Plaid](docs/api-setup.md#plaid-api-setup) for banking
- 📊 [Connect QuickBooks](docs/api-setup.md#quickbooks-api-setup) for accounting

### Scale Up:
- 💾 [Add PostgreSQL database](docs/deployment.md#database-setup)
- 🌐 [Deploy to production](docs/deployment.md#deployment-options)
- 👥 [Add user registration](docs/features.md#user-management)

---

## 💡 Pro Tips

### 1. Keyboard Shortcuts
- `Ctrl+R` (or `Cmd+R`) - Refresh app
- `Ctrl+Shift+R` - Hard refresh (clear cache)

### 2. Debug Mode
Add to your code:
```python
if st.checkbox("Debug Mode"):
    st.json(st.session_state)
```

### 3. Speed Up Development
```python
# Cache expensive operations
@st.cache_data(ttl=300)
def expensive_calculation():
    return result
```

### 4. Better Error Handling
```python
try:
    result = ai_analysis()
except Exception as e:
    st.error(f"AI analysis failed: {e}")
    st.info("Using fallback analysis...")
```

---

## 🤝 Getting Help

### Quick Help:
- **GitHub Issues**: [Report bugs](https://github.com/yourusername/ai-cfo-mvp/issues)
- **Discord**: Join our [developer community](#)
- **Email**: support@your-domain.com

### Common Questions:
- **"Can I use real bank data?"** → Yes! Set up Plaid API
- **"How much does it cost to run?"** → $0-10/month depending on deployment
- **"Is my data secure?"** → Yes, runs locally or in your cloud account
- **"Can I customize for my industry?"** → Absolutely! Modify prompts and data models

---

**🎉 Congratulations! You now have a working AI CFO system.**

*Start exploring, customizing, and building the future of financial intelligence!*

---

**⭐ Like this project? Star us on GitHub and share with other founders!**

*Last updated: December 2024*