# app.py - Main Streamlit Application
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

from database_module import DatabaseManager
from supporting_modules import CashFlowAgent, PlaidClient, QuickBooksClient, DeepSeekClient, AuthSystem

# Configure page
st.set_page_config(
    page_title="AI CFO - Financial Intelligence",
    page_icon="💰",
    layout="wide"
)

def init_session_state():
    """Initialize session state objects"""
    if 'db' not in st.session_state:
        st.session_state.db = DatabaseManager()
    
    if 'auth' not in st.session_state:
        st.session_state.auth = AuthSystem(st.session_state.db)
    
    if 'plaid' not in st.session_state:
        st.session_state.plaid = PlaidClient()
    
    if 'qb' not in st.session_state:
        st.session_state.qb = QuickBooksClient()
    
    if 'ai' not in st.session_state:
        st.session_state.ai = DeepSeekClient()

def show_login():
    """Login interface"""
    st.title("🏢 AI CFO Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        
        if st.button("Login", type="primary", use_container_width=True):
            user = st.session_state.auth.authenticate(username, password)
            if user:
                st.session_state.user = user
                st.success(f"Welcome, {user['full_name']}!")
                st.rerun()
            else:
                st.error("Invalid credentials")
        
        # Demo accounts
        st.markdown("---")
        st.markdown("**Demo Accounts:**")
        demo_accounts = st.session_state.db.get_demo_accounts()
        for account in demo_accounts:
            st.code(f"{account['username']} / {account['password']} - {account['role']} @ {account['company_name']}")

def show_dashboard(user):
    """Main dashboard"""
    # Header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.title(f"💰 AI CFO - {user['company_name']}")
        st.caption(f"{user['industry']} • {user['employee_count']} employees")
    
    with col2:
        st.metric("Your Role", user['role'])
    
    with col3:
        if st.button("🚪 Logout"):
            del st.session_state.user
            st.rerun()
    
    # Sidebar navigation
    st.sidebar.title(f"🏢 {user['company_name']}")
    
    # Role-based pages
    if user['role'] in ['CEO', 'CFO']:
        pages = ["Executive Dashboard", "Banking", "Cash Flow", "AR Management", "AP Management", "AI Chat"]
    elif user['role'] == 'Accountant':
        pages = ["Banking", "Transactions", "AR Management", "AP Management"]
    else:
        pages = ["Banking", "Transactions"]
    
    page = st.sidebar.selectbox("Navigation", pages)
    
    # Initialize agent
    agent = CashFlowAgent(st.session_state.db, st.session_state.plaid, 
                         st.session_state.qb, st.session_state.ai)
    
    # Route to pages
    if page == "Executive Dashboard":
        show_executive_dashboard(user, agent)
    elif page == "Banking":
        show_banking_page(user, agent)
    elif page == "Cash Flow":
        show_cash_flow_page(user, agent)
    elif page == "AR Management":
        show_ar_page(user, agent)
    elif page == "AP Management":
        show_ap_page(user, agent)
    elif page == "AI Chat":
        show_ai_chat(user, agent)
    elif page == "Transactions":
        show_transactions_page(user, agent)

def show_executive_dashboard(user, agent):
    """Executive dashboard"""
    st.header("📊 Executive Dashboard")
    
    # Get financial data
    financial_data = agent.get_financial_summary(user['company_id'])
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Current Cash", f"${financial_data['current_cash']:,.0f}")
    
    with col2:
        st.metric("🏃‍♂️ Cash Runway", f"{financial_data['runway_days']} days")
    
    with col3:
        st.metric("📄 Outstanding AR", f"${financial_data['outstanding_ar']:,.0f}")
    
    with col4:
        st.metric("💳 Upcoming AP", f"${financial_data['upcoming_ap']:,.0f}")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💸 Cash Flow Trend")
        cash_flow_data = agent.get_cash_flow_chart_data(user['company_id'])
        if cash_flow_data:
            df = pd.DataFrame(cash_flow_data)
            fig = px.line(df, x='date', y='balance', title='Cash Balance Over Time')
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🎯 Expense Breakdown")
        expense_data = agent.get_expense_breakdown(user['company_id'])
        if expense_data:
            df = pd.DataFrame(expense_data)
            fig = px.pie(df, values='amount', names='category', title='Expense Categories')
            st.plotly_chart(fig, use_container_width=True)
    
    # AI Insights
    st.subheader("🤖 AI Insights")
    if st.button("Get AI Analysis"):
        with st.spinner("Analyzing financial data..."):
            insights = agent.get_ai_insights(user['company_id'], user['company_name'])
            st.markdown(insights)

def show_banking_page(user, agent):
    """Banking overview"""
    st.header("🏦 Banking Overview")
    
    # Data sync status
    with st.expander("🔄 Data Sync Status"):
        sync_status = st.session_state.db.get_sync_status(user['company_id'])
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if sync_status['plaid_last_sync']:
                st.success(f"✅ Bank: {sync_status['plaid_last_sync']}")
            else:
                st.warning("⚠️ Bank: Not connected")
        
        with col2:
            if sync_status['qb_last_sync']:
                st.success(f"✅ Accounting: {sync_status['qb_last_sync']}")
            else:
                st.warning("⚠️ Accounting: Not connected")
        
        with col3:
            if st.button("🔄 Sync Data"):
                sync_data(user['company_id'])
                st.success("Data synced!")
                st.rerun()
    
    # Account balances
    accounts = st.session_state.db.get_accounts(user['company_id'])
    
    if accounts:
        st.subheader("💳 Account Balances")
        
        for account in accounts:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                st.write(f"**{account['name']}**")
                st.caption(f"{account['institution_name']}")
            
            with col2:
                st.metric("Balance", f"${account['current_balance']:,.2f}")
            
            with col3:
                st.metric("Available", f"${account['available_balance']:,.2f}")
            
            with col4:
                st.write(f"**Type:** {account['type'].title()}")
    
    # Recent transactions
    st.subheader("🔄 Recent Transactions")
    transactions = st.session_state.db.get_recent_transactions(user['company_id'], limit=10)
    
    if transactions:
        df = pd.DataFrame(transactions)
        df['amount'] = df['amount'].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df[['date', 'merchant_name', 'amount', 'category']], 
                    use_container_width=True, hide_index=True)

def show_cash_flow_page(user, agent):
    """Cash flow analysis"""
    st.header("💸 Cash Flow Analysis")
    
    financial_data = agent.get_financial_summary(user['company_id'])
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Current Cash", f"${financial_data['current_cash']:,.0f}")
        st.metric("Monthly Burn", f"${financial_data['monthly_burn']:,.0f}")
    
    with col2:
        st.metric("Cash Runway", f"{financial_data['runway_days']} days")
        st.metric("Monthly Income", f"${financial_data['monthly_income']:,.0f}")
    
    with col3:
        net_flow = financial_data['monthly_income'] - financial_data['monthly_burn']
        st.metric("Net Cash Flow", f"${net_flow:,.0f}")
    
    # 13-week projection
    st.subheader("📈 13-Week Cash Flow Projection")
    projection = agent.generate_cash_flow_projection(user['company_id'])
    
    if projection:
        df = pd.DataFrame(projection)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df['week'], y=df['projected_cash'], 
                                mode='lines+markers', name='Projected Cash'))
        fig.add_hline(y=0, line_dash="dash", line_color="red", 
                      annotation_text="Cash Depletion")
        fig.update_layout(title="Cash Flow Projection", 
                         xaxis_title="Weeks", yaxis_title="Cash ($)")
        st.plotly_chart(fig, use_container_width=True)

def show_ar_page(user, agent):
    """AR management"""
    st.header("📄 Accounts Receivable")
    
    invoices = st.session_state.db.get_invoices(user['company_id'])
    
    if invoices:
        # Summary
        total_ar = sum(inv['balance'] for inv in invoices if inv['balance'] > 0)
        overdue_ar = sum(inv['balance'] for inv in invoices if inv['days_overdue'] > 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total AR", f"${total_ar:,.0f}")
        with col2:
            st.metric("Overdue", f"${overdue_ar:,.0f}")
        with col3:
            overdue_count = len([inv for inv in invoices if inv['days_overdue'] > 0])
            st.metric("Overdue Count", overdue_count)
        
        # Invoices table
        df = pd.DataFrame(invoices)
        df['amount'] = df['amount'].apply(lambda x: f"${x:,.0f}")
        df['balance'] = df['balance'].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(df[['invoice_number', 'customer_name', 'amount', 
                        'balance', 'due_date', 'days_overdue']], 
                    use_container_width=True, hide_index=True)

def show_ap_page(user, agent):
    """AP management"""
    st.header("💳 Accounts Payable")
    
    bills = st.session_state.db.get_bills(user['company_id'])
    
    if bills:
        # Summary
        total_ap = sum(bill['balance'] for bill in bills if bill['balance'] > 0)
        due_soon = sum(bill['balance'] for bill in bills 
                      if bill['balance'] > 0 and 
                      (datetime.strptime(bill['due_date'], '%Y-%m-%d') - datetime.now()).days <= 7)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total AP", f"${total_ap:,.0f}")
        with col2:
            st.metric("Due This Week", f"${due_soon:,.0f}")
        with col3:
            urgent_count = len([bill for bill in bills 
                              if bill['balance'] > 0 and 
                              (datetime.strptime(bill['due_date'], '%Y-%m-%d') - datetime.now()).days <= 7])
            st.metric("Urgent Bills", urgent_count)
        
        # Bills table
        df = pd.DataFrame(bills)
        df['amount'] = df['amount'].apply(lambda x: f"${x:,.0f}")
        df['balance'] = df['balance'].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(df[['bill_number', 'vendor_name', 'amount', 
                        'balance', 'due_date', 'category']], 
                    use_container_width=True, hide_index=True)

def show_transactions_page(user, agent):
    """Transactions management"""
    st.header("💳 Transactions")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        days = st.selectbox("Period", [7, 14, 30, 60])
    with col2:
        min_amount = st.number_input("Min Amount", value=0.0)
    with col3:
        tx_type = st.selectbox("Type", ["All", "Income", "Expenses"])
    
    # Get transactions
    transactions = st.session_state.db.get_transactions(
        user['company_id'], days=days, min_amount=min_amount, tx_type=tx_type
    )
    
    if transactions:
        # Summary
        total_income = sum(tx['amount'] for tx in transactions if tx['amount'] > 0)
        total_expenses = sum(abs(tx['amount']) for tx in transactions if tx['amount'] < 0)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Transactions", len(transactions))
        with col2:
            st.metric("Income", f"${total_income:,.0f}")
        with col3:
            st.metric("Expenses", f"${total_expenses:,.0f}")
        
        # Transactions table
        df = pd.DataFrame(transactions)
        df['amount'] = df['amount'].apply(lambda x: f"${x:,.2f}")
        
        st.dataframe(df[['date', 'merchant_name', 'amount', 'category']], 
                    use_container_width=True, hide_index=True)

def show_ai_chat(user, agent):
    """AI chat interface"""
    st.header("🤖 AI Financial Assistant")
    
    # Quick buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("💰 Cash Analysis", use_container_width=True):
            st.session_state.quick_question = "Analyze my current cash flow situation"
    
    with col2:
        if st.button("📊 Financial Health", use_container_width=True):
            st.session_state.quick_question = "Assess my company's financial health"
    
    with col3:
        if st.button("🎯 Recommendations", use_container_width=True):
            st.session_state.quick_question = "What are your top 3 recommendations?"
    
    # Chat interface
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # Display messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Handle quick questions
    if 'quick_question' in st.session_state:
        prompt = st.session_state.quick_question
        del st.session_state.quick_question
        
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = agent.get_ai_insights(user['company_id'], user['company_name'], prompt)
                st.markdown(response)
        
        st.session_state.chat_messages.append({"role": "assistant", "content": response})
    
    # Chat input
    if prompt := st.chat_input("Ask about your finances..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = agent.get_ai_insights(user['company_id'], user['company_name'], prompt)
                st.markdown(response)
        
        st.session_state.chat_messages.append({"role": "assistant", "content": response})

def sync_data(company_id):
    """Sync data from external APIs"""
    from data_sync_script import sync_plaid_data, sync_quickbooks_data
    
    # Sync Plaid data
    try:
        sync_plaid_data(company_id)
        st.success("✅ Bank data synced")
    except Exception as e:
        st.warning(f"⚠️ Bank sync failed: {e}")
    
    # Sync QuickBooks data
    try:
        sync_quickbooks_data(company_id)
        st.success("✅ Accounting data synced")
    except Exception as e:
        st.warning(f"⚠️ Accounting sync failed: {e}")

def main():
    init_session_state()
    
    if 'user' not in st.session_state:
        show_login()
    else:
        show_dashboard(st.session_state.user)

if __name__ == "__main__":
    main()