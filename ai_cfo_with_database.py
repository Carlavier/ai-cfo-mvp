# AI CFO MVP with Database & DeepSeek API
# Requirements: streamlit, sqlite3, requests, plotly, pandas

import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import json
import hashlib
import os
from typing import Dict, List, Optional
import random

# Configure page
st.set_page_config(
    page_title="AI CFO - Financial Intelligence",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database Schema & Setup
class DatabaseManager:
    def __init__(self, db_path="ai_cfo.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def init_database(self):
        """Initialize database with all required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                company_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Companies table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                industry TEXT,
                plaid_access_token TEXT,
                qb_access_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bank accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                plaid_account_id TEXT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                subtype TEXT,
                current_balance REAL DEFAULT 0,
                available_balance REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                plaid_transaction_id TEXT,
                amount REAL NOT NULL,
                date DATE NOT NULL,
                merchant_name TEXT,
                category TEXT,
                subcategory TEXT,
                pending BOOLEAN DEFAULT FALSE,
                ai_category TEXT,
                ai_confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES bank_accounts (id)
            )
        ''')
        
        # Invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                qb_invoice_id TEXT,
                customer_name TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                due_date DATE,
                issue_date DATE,
                status TEXT DEFAULT 'pending',
                days_overdue INTEGER DEFAULT 0,
                ai_collection_score REAL,
                last_reminder_sent DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        ''')
        
        # Bills table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                qb_bill_id TEXT,
                vendor_name TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                due_date DATE,
                category TEXT,
                status TEXT DEFAULT 'pending',
                priority_score REAL,
                ai_recommendation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        ''')
        
        # AI insights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                insight_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                confidence_score REAL,
                action_required BOOLEAN DEFAULT FALSE,
                is_dismissed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        ''')
        
        # Chat history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                user_id INTEGER,
                question TEXT NOT NULL,
                response TEXT NOT NULL,
                response_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Insert default data if tables are empty
        self.insert_default_data()
    
    def insert_default_data(self):
        """Insert sample data for demo"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM companies")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return
        
        # Insert demo company
        cursor.execute('''
            INSERT INTO companies (name, industry) 
            VALUES ('TechStartup Inc', 'Technology')
        ''')
        company_id = cursor.lastrowid
        
        # Insert demo users
        users_data = [
            ('ceo', 'ceo123', 'CEO', company_id),
            ('cfo', 'cfo123', 'CFO', company_id),
            ('accountant', 'acc123', 'Accountant', company_id),
            ('manager', 'mgr123', 'Manager', company_id),
            ('employee', 'emp123', 'Employee', company_id)
        ]
        
        for username, password, role, comp_id in users_data:
            password_hash = hashlib.md5(password.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, password_hash, role, company_id) 
                VALUES (?, ?, ?, ?)
            ''', (username, password_hash, role, comp_id))
        
        # Insert demo bank accounts
        accounts_data = [
            (company_id, 'acc_001', 'Business Checking - Wells Fargo', 'depository', 'checking', 47332.25, 45000.50),
            (company_id, 'acc_002', 'Business Savings - Wells Fargo', 'depository', 'savings', 125000.00, 125000.00),
            (company_id, 'acc_003', 'Credit Line - Chase', 'credit', 'line_of_credit', -8500.00, 41500.00)
        ]
        
        for acc_data in accounts_data:
            cursor.execute('''
                INSERT INTO bank_accounts (company_id, plaid_account_id, name, type, subtype, current_balance, available_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', acc_data)
        
        # Insert demo transactions
        merchants = [
            ("Amazon Web Services", "Service,Cloud Computing", -2500.00),
            ("Office Depot", "Office Supplies", -1200.00),
            ("Stripe Payment", "Revenue,Payment", 15000.00),
            ("Google Ads", "Marketing,Advertising", -3200.00),
            ("Slack Technologies", "Software,Communication", -840.00),
            ("ABC Corp - Wire Transfer", "Revenue,Client Payment", 25000.00),
            ("Uber for Business", "Travel,Transportation", -450.00),
            ("Microsoft Office 365", "Software,Productivity", -299.00)
        ]
        
        for i in range(50):
            merchant, category, base_amount = random.choice(merchants)
            amount = base_amount + random.uniform(-100, 100)
            date = (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d")
            account_id = random.randint(1, 3)
            
            cursor.execute('''
                INSERT INTO transactions (account_id, plaid_transaction_id, amount, date, merchant_name, category, pending)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (account_id, f'txn_{i+1:03d}', amount, date, merchant, category, False))
        
        # Insert demo invoices
        customers = [
            ("ABC Corporation", 8500.00, 8500.00, 45, "overdue"),
            ("XYZ Tech Solutions", 12000.00, 12000.00, 15, "pending"),
            ("StartupCo", 5500.00, 0.00, -5, "paid"),
            ("Enterprise LLC", 25000.00, 25000.00, 30, "overdue"),
            ("SmallBiz Inc", 3200.00, 3200.00, 10, "pending")
        ]
        
        for customer, amount, balance, days_diff, status in customers:
            due_date = (datetime.now() + timedelta(days=days_diff)).strftime("%Y-%m-%d")
            issue_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            days_overdue = max(0, -days_diff) if status == "overdue" else 0
            
            cursor.execute('''
                INSERT INTO invoices (company_id, customer_name, amount, balance, due_date, issue_date, status, days_overdue)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company_id, customer, amount, balance, due_date, issue_date, status, days_overdue))
        
        # Insert demo bills
        vendors = [
            ("Office Depot", 1200.00, 1200.00, 3, "Office Supplies", "pending"),
            ("Amazon Web Services", 2500.00, 2500.00, 15, "Cloud Services", "pending"),
            ("Google Workspace", 299.00, 299.00, 25, "Software", "pending"),
            ("Stripe", 450.00, 450.00, 1, "Payment Processing", "urgent"),
            ("Landlord - Office Rent", 8500.00, 8500.00, 5, "Rent", "pending")
        ]
        
        for vendor, amount, balance, days_until_due, category, status in vendors:
            due_date = (datetime.now() + timedelta(days=days_until_due)).strftime("%Y-%m-%d")
            
            cursor.execute('''
                INSERT INTO bills (company_id, vendor_name, amount, balance, due_date, category, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (company_id, vendor, amount, balance, due_date, category, status))
        
        conn.commit()
        conn.close()

# DeepSeek API Client
class DeepSeekClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY', 'your_deepseek_key_here')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
    
    def analyze_financial_data(self, query: str, context_data: Dict) -> str:
        """Use DeepSeek to analyze financial data and provide insights"""
        
        system_prompt = """You are an expert AI CFO assistant. Analyze the provided financial data and answer questions with specific numbers, actionable insights, and clear recommendations. 

Key principles:
1. Always use actual numbers from the data provided
2. Give specific, actionable recommendations
3. Highlight risks and opportunities
4. Keep responses concise but comprehensive
5. Format important numbers clearly (e.g., $12,500)"""
        
        user_prompt = f"""
        Financial Data Context:
        {json.dumps(context_data, indent=2)}
        
        User Question: {query}
        
        Please provide a detailed analysis with specific recommendations.
        """
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }
            
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                # Fallback to rule-based response
                return self.fallback_analysis(query, context_data)
                
        except Exception as e:
            st.error(f"DeepSeek API Error: {e}")
            return self.fallback_analysis(query, context_data)
    
    def fallback_analysis(self, query: str, context_data: Dict) -> str:
        """Fallback analysis when API fails"""
        query_lower = query.lower()
        
        if "cash" in query_lower and "runway" in query_lower:
            cash = context_data.get('current_cash', 0)
            monthly_burn = context_data.get('monthly_burn', 25000)
            runway_days = int(cash / (monthly_burn / 30)) if monthly_burn > 0 else 999
            
            return f"""**Cash Runway Analysis:**
- Current cash position: ${cash:,.0f}
- Monthly burn rate: ${monthly_burn:,.0f}
- **Cash runway: {runway_days} days**

**Recommendations:**
- {"⚠️ Critical: Runway below 90 days. Reduce expenses immediately." if runway_days < 90 else "✅ Healthy runway. Monitor monthly."}
- Focus on collecting overdue receivables to extend runway
- Review non-essential expenses for potential cuts"""
        
        elif "overdue" in query_lower or "receivable" in query_lower:
            overdue_amount = context_data.get('total_overdue', 0)
            overdue_count = context_data.get('overdue_count', 0)
            
            return f"""**Accounts Receivable Analysis:**
- Total overdue: ${overdue_amount:,.0f}
- Number of overdue invoices: {overdue_count}

**Immediate Actions:**
1. Contact customers with largest overdue amounts
2. Offer payment plans for amounts over $5,000
3. Consider collection agency for 60+ day overdue accounts
4. Implement automated reminder system"""
        
        else:
            return f"""I can help you analyze:
- Cash flow and runway calculations
- Accounts receivable management  
- Expense categorization and trends
- Revenue forecasting
- Bill payment prioritization

Please ask specific questions about your financial data."""

# Enhanced AI Agents with Database Integration
class EnhancedCashFlowAgent:
    def __init__(self, db_manager: DatabaseManager, deepseek_client: DeepSeekClient):
        self.db = db_manager
        self.ai = deepseek_client
    
    def get_cash_position(self, company_id: int) -> Dict:
        """Get real-time cash position from database"""
        conn = self.db.get_connection()
        
        # Get total cash from bank accounts
        query = """
            SELECT SUM(current_balance) as total_cash,
                   SUM(available_balance) as available_cash
            FROM bank_accounts 
            WHERE company_id = ? AND type IN ('depository')
        """
        
        cash_result = pd.read_sql_query(query, conn, params=(company_id,))
        total_cash = cash_result['total_cash'].iloc[0] or 0
        available_cash = cash_result['available_cash'].iloc[0] or 0
        
        # Get outstanding receivables
        ar_query = """
            SELECT SUM(balance) as total_ar
            FROM invoices 
            WHERE company_id = ? AND status != 'paid'
        """
        
        ar_result = pd.read_sql_query(ar_query, conn, params=(company_id,))
        outstanding_ar = ar_result['total_ar'].iloc[0] or 0
        
        # Get upcoming payables
        ap_query = """
            SELECT SUM(balance) as total_ap
            FROM bills 
            WHERE company_id = ? AND status = 'pending'
        """
        
        ap_result = pd.read_sql_query(ap_query, conn, params=(company_id,))
        upcoming_ap = ap_result['total_ap'].iloc[0] or 0
        
        # Calculate monthly burn (last 30 days expenses)
        burn_query = """
            SELECT SUM(ABS(amount)) as monthly_expenses
            FROM transactions t
            JOIN bank_accounts ba ON t.account_id = ba.id
            WHERE ba.company_id = ? AND t.amount < 0 
            AND t.date >= date('now', '-30 days')
        """
        
        burn_result = pd.read_sql_query(burn_query, conn, params=(company_id,))
        monthly_burn = burn_result['monthly_expenses'].iloc[0] or 28500
        
        # Calculate runway
        runway_days = int(total_cash / (monthly_burn / 30)) if monthly_burn > 0 else 999
        
        conn.close()
        
        return {
            "current_cash": total_cash,
            "available_cash": available_cash,
            "outstanding_ar": outstanding_ar,
            "upcoming_ap": upcoming_ap,
            "net_cash_position": total_cash + outstanding_ar - upcoming_ap,
            "monthly_burn": monthly_burn,
            "runway_days": runway_days
        }
    
    def get_ai_cash_insights(self, company_id: int, user_question: str = None) -> str:
        """Get AI-powered cash flow insights"""
        cash_data = self.get_cash_position(company_id)
        
        if not user_question:
            user_question = "Analyze my current cash flow situation and provide recommendations"
        
        return self.ai.analyze_financial_data(user_question, cash_data)

# Authentication System
class AuthSystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return user info"""
        conn = self.db.get_connection()
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        query = """
            SELECT u.id, u.username, u.role, u.company_id, c.name as company_name
            FROM users u
            JOIN companies c ON u.company_id = c.id
            WHERE u.username = ? AND u.password_hash = ?
        """
        
        result = pd.read_sql_query(query, conn, params=(username, password_hash))
        conn.close()
        
        if len(result) > 0:
            return result.iloc[0].to_dict()
        return None

# Streamlit App with Database Integration
def main():
    # Initialize database and clients
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()
    
    if 'deepseek_client' not in st.session_state:
        st.session_state.deepseek_client = DeepSeekClient()
    
    if 'auth_system' not in st.session_state:
        st.session_state.auth_system = AuthSystem(st.session_state.db_manager)
    
    # Authentication
    if 'user' not in st.session_state:
        show_login_page()
        return
    
    # Main app
    user = st.session_state.user
    show_main_dashboard(user)

def show_login_page():
    """Login interface"""
    st.title("🔐 AI CFO Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Welcome to AI CFO System")
        
        username = st.text_input("Username", placeholder="e.g., ceo")
        password = st.text_input("Password", type="password", placeholder="e.g., ceo123")
        
        if st.button("Login", type="primary", use_container_width=True):
            user = st.session_state.auth_system.authenticate_user(username, password)
            
            if user:
                st.session_state.user = user
                st.success(f"Welcome, {user['username']}!")
                st.rerun()
            else:
                st.error("Invalid username or password")
        
        st.markdown("---")
        st.markdown("**Demo Accounts:**")
        st.code("""
CEO: ceo / ceo123
CFO: cfo / cfo123  
Accountant: accountant / acc123
Manager: manager / mgr123
Employee: employee / emp123
        """)

def show_main_dashboard(user):
    """Main dashboard with role-based access"""
    
    # Header
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.title(f"💰 AI CFO - {user['company_name']}")
    with col2:
        st.write(f"**Role:** {user['role']}")
    with col3:
        if st.button("Logout"):
            del st.session_state.user
            st.rerun()
    
    # Navigation
    st.sidebar.title(f"👋 {user['username']}")
    
    # Role-based navigation
    role_pages = {
        "CEO": ["Executive Dashboard", "AI Chat", "Financial Reports"],
        "CFO": ["Executive Dashboard", "Cash Flow", "AR Management", "AP Management", "AI Chat", "Financial Reports"],
        "Accountant": ["Transaction Management", "AR Management", "AP Management", "AI Chat"],
        "Manager": ["Department View", "Expense Requests", "AI Chat"],
        "Employee": ["Expense Submission", "My Transactions"]
    }
    
    available_pages = role_pages.get(user['role'], ["AI Chat"])
    page = st.sidebar.selectbox("Navigation", available_pages)
    
    # Page routing
    if page == "Executive Dashboard":
        show_executive_dashboard(user)
    elif page == "Cash Flow":
        show_cash_flow_page(user)
    elif page == "AR Management":
        show_ar_management_page(user)
    elif page == "AP Management":
        show_ap_management_page(user)
    elif page == "AI Chat":
        show_ai_chat_page(user)
    elif page == "Transaction Management":
        show_transaction_management_page(user)
    elif page == "Financial Reports":
        show_financial_reports_page(user)
    else:
        st.info(f"Page '{page}' is under development")

def show_executive_dashboard(user):
    """Executive dashboard with real data"""
    st.header("📊 Executive Dashboard")
    
    # Initialize agents
    cash_agent = EnhancedCashFlowAgent(st.session_state.db_manager, st.session_state.deepseek_client)
    cash_data = cash_agent.get_cash_position(user['company_id'])
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Current Cash", f"${cash_data['current_cash']:,.0f}", 
                 delta=f"+${random.randint(2000, 8000):,}")
    
    with col2:
        st.metric("🏃‍♂️ Cash Runway", f"{cash_data['runway_days']} days",
                 delta=f"{random.randint(-15, 25):+} days")
    
    with col3:
        st.metric("📄 Outstanding AR", f"${cash_data['outstanding_ar']:,.0f}",
                 delta="3 overdue")
    
    with col4:
        st.metric("💳 Upcoming AP", f"${cash_data['upcoming_ap']:,.0f}",
                 delta="5 bills due")
    
    # AI Insights Section
    st.subheader("🤖 AI Financial Insights")
    
    with st.expander("💡 Get AI Analysis", expanded=True):
        insight_question = st.selectbox(
            "Quick Analysis:",
            [
                "Analyze my current cash runway and provide recommendations",
                "What are my biggest financial risks right now?",
                "How can I improve cash flow this month?",
                "Should I be concerned about any overdue invoices?"
            ]
        )
        
        if st.button("Get AI Insights"):
            with st.spinner("AI analyzing your financial data..."):
                insights = cash_agent.get_ai_cash_insights(user['company_id'], insight_question)
                st.markdown(insights)

def show_cash_flow_page(user):
    """Detailed cash flow analysis"""
    st.header("💸 Cash Flow Analysis")
    
    cash_agent = EnhancedCashFlowAgent(st.session_state.db_manager, st.session_state.deepseek_client)
    cash_data = cash_agent.get_cash_position(user['company_id'])
    
    # Detailed metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Current Cash", f"${cash_data['current_cash']:,.0f}")
        st.metric("Available Cash", f"${cash_data['available_cash']:,.0f}")
    
    with col2:
        st.metric("Outstanding AR", f"${cash_data['outstanding_ar']:,.0f}")
        st.metric("Upcoming AP", f"${cash_data['upcoming_ap']:,.0f}")
    
    with col3:
        st.metric("Net Position", f"${cash_data['net_cash_position']:,.0f}")
        st.metric("Monthly Burn", f"${cash_data['monthly_burn']:,.0f}")
    
    # Cash flow chart (using recent transactions)
    st.subheader("📈 Cash Flow Trend")
    
    conn = st.session_state.db_manager.get_connection()
    transaction_query = """
        SELECT 
            DATE(t.date) as date,
            SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END) as inflow,
            SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END) as outflow
        FROM transactions t
        JOIN bank_accounts ba ON t.account_id = ba.id
        WHERE ba.company_id = ?
        AND t.date >= date('now', '-30 days')
        GROUP BY DATE(t.date)
        ORDER BY date
    """
    
    df_flow = pd.read_sql_query(transaction_query, conn, params=(user['company_id'],))
    conn.close()
    
    if not df_flow.empty:
        df_flow['net_flow'] = df_flow['inflow'] - df_flow['outflow']
        df_flow['cumulative_flow'] = df_flow['net_flow'].cumsum() + cash_data['current_cash']
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_flow['date'], y=df_flow['cumulative_flow'],
                                mode='lines+markers', name='Cash Balance', 
                                line=dict(color='blue', width=3)))
        
        fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Zero Cash")
        fig.update_layout(title="30-Day Cash Flow", xaxis_title="Date", yaxis_title="Cash ($)")
        
        st.plotly_chart(fig, use_container_width=True)

def show_ai_chat_page(user):
    """Enhanced AI chat with DeepSeek"""
    st.header("🤖 AI CFO Assistant")
    
    # Get financial context for AI
    cash_agent = EnhancedCashFlowAgent(st.session_state.db_manager, st.session_state.deepseek_client)
    
    # Chat interface
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me about your finances..."):
        # Add user message
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing your financial data..."):
                response = cash_agent.get_ai_cash_insights(user['company_id'], prompt)
                st.markdown(response)
                
                # Save to database
                conn = st.session_state.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO chat_history (company_id, user_id, question, response)
                    VALUES (?, ?, ?, ?)
                ''', (user['company_id'], user['id'], prompt, response))
                conn.commit()
                conn.close()
        
        # Add assistant response
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

def show_ar_management_page(user):
    """AR management with database integration"""
    st.header("📄 Accounts Receivable Management")
    
    conn = st.session_state.db_manager.get_connection()
    
    # Get overdue invoices
    overdue_query = """
        SELECT customer_name, amount, balance, due_date, days_overdue
        FROM invoices 
        WHERE company_id = ? AND status = 'overdue'
        ORDER BY amount DESC
    """
    
    df_overdue = pd.read_sql_query(overdue_query, conn, params=(user['company_id'],))
    
    if not df_overdue.empty:
        st.subheader("⚠️ Overdue Invoices")
        
        # Format the dataframe
        df_display = df_overdue.copy()
        df_display['amount'] = df_display['amount'].apply(lambda x: f"${x:,.0f}")
        df_display['balance'] = df_display['balance'].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(df_display, use_container_width=True)
        
        # AI recommendations
        st.subheader("🤖 AI Collection Recommendations")
        total_overdue = df_overdue['balance'].sum()
        avg_days = df_overdue['days_overdue'].mean()
        
        ai_prompt = f"I have ${total_overdue:,.0f} in overdue receivables with average {avg_days:.0f} days overdue. What should I do?"
        
        if st.button("Get AI Recommendations"):
            cash_agent = EnhancedCashFlowAgent(st.session_state.db_manager, st.session_state.deepseek_client)
            recommendations = cash_agent.get_ai_cash_insights(user['company_id'], ai_prompt)
            st.markdown(recommendations)
    
    else:
        st.success("🎉 No overdue invoices!")
    
    conn.close()

def show_transaction_management_page(user):
    """Transaction management for accountants"""
    st.header("💳 Transaction Management")
    
    conn = st.session_state.db_manager.get_connection()
    
    # Get recent transactions
    trans_query = """
        SELECT t.date, t.merchant_name, t.amount, t.category, 
               CASE WHEN t.amount > 0 THEN 'Income' ELSE 'Expense' END as type
        FROM transactions t
        JOIN bank_accounts ba ON t.account_id = ba.id
        WHERE ba.company_id = ?
        ORDER BY t.date DESC
        LIMIT 50
    """
    
    df_trans = pd.read_sql_query(trans_query, conn, params=(user['company_id'],))
    
    if not df_trans.empty:
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        total_income = df_trans[df_trans['amount'] > 0]['amount'].sum()
        total_expenses = df_trans[df_trans['amount'] < 0]['amount'].abs().sum()
        net_flow = total_income - total_expenses
        
        with col1:
            st.metric("💰 Total Income", f"${total_income:,.0f}")
        with col2:
            st.metric("💸 Total Expenses", f"${total_expenses:,.0f}")
        with col3:
            st.metric("📊 Net Flow", f"${net_flow:,.0f}")
        
        # Transactions table
        st.subheader("Recent Transactions")
        df_display = df_trans.copy()
        df_display['amount'] = df_display['amount'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(df_display, use_container_width=True)
    
    conn.close()

def show_ap_management_page(user):
    """AP management page"""
    st.header("💳 Accounts Payable Management")
    
    conn = st.session_state.db_manager.get_connection()
    
    # Get pending bills
    bills_query = """
        SELECT vendor_name, amount, balance, due_date, category,
               julianday(due_date) - julianday('now') as days_until_due
        FROM bills 
        WHERE company_id = ? AND status = 'pending'
        ORDER BY due_date
    """
    
    df_bills = pd.read_sql_query(bills_query, conn, params=(user['company_id'],))
    
    if not df_bills.empty:
        # Summary
        total_ap = df_bills['balance'].sum()
        urgent_bills = df_bills[df_bills['days_until_due'] <= 7]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total AP", f"${total_ap:,.0f}")
        with col2:
            st.metric("Urgent Bills", len(urgent_bills))
        with col3:
            st.metric("This Week", f"${urgent_bills['balance'].sum():,.0f}")
        
        # Bills table with priority highlighting
        st.subheader("📋 Pending Bills")
        
        def highlight_urgent(row):
            if row['days_until_due'] <= 3:
                return ['background-color: #ffebee'] * len(row)
            elif row['days_until_due'] <= 7:
                return ['background-color: #fff3e0'] * len(row)
            return [''] * len(row)
        
        df_display = df_bills.copy()
        df_display['amount'] = df_display['amount'].apply(lambda x: f"${x:,.0f}")
        df_display['balance'] = df_display['balance'].apply(lambda x: f"${x:,.0f}")
        df_display['days_until_due'] = df_display['days_until_due'].apply(lambda x: f"{x:.0f} days")
        
        st.dataframe(df_display.style.apply(highlight_urgent, axis=1), use_container_width=True)
    
    conn.close()

def show_financial_reports_page(user):
    """Financial reports page"""
    st.header("📊 Financial Reports")
    
    conn = st.session_state.db_manager.get_connection()
    
    # Monthly summary
    st.subheader("📈 Monthly Summary")
    
    monthly_query = """
        SELECT 
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as revenue,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as expenses
        FROM transactions t
        JOIN bank_accounts ba ON t.account_id = ba.id
        WHERE ba.company_id = ?
        AND date >= date('now', 'start of month')
    """
    
    monthly_data = pd.read_sql_query(monthly_query, conn, params=(user['company_id'],))
    
    if not monthly_data.empty:
        revenue = monthly_data['revenue'].iloc[0] or 0
        expenses = monthly_data['expenses'].iloc[0] or 0
        profit = revenue - expenses
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📈 Revenue", f"${revenue:,.0f}")
        with col2:
            st.metric("📉 Expenses", f"${expenses:,.0f}")
        with col3:
            st.metric("💰 Profit", f"${profit:,.0f}", delta=f"{profit/revenue*100:.1f}%" if revenue > 0 else "0%")
        
        # Revenue vs Expenses Chart
        fig = go.Figure(data=[
            go.Bar(name='Revenue', x=['This Month'], y=[revenue], marker_color='green'),
            go.Bar(name='Expenses', x=['This Month'], y=[expenses], marker_color='red')
        ])
        fig.update_layout(title="Revenue vs Expenses", barmode='group')
        st.plotly_chart(fig, use_container_width=True)
    
    conn.close()

if __name__ == "__main__":
    main()