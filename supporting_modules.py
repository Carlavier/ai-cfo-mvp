# auth.py - Authentication System
import hashlib
import pandas as pd
from typing import Optional, Dict
from database_module import DatabaseManager

class AuthSystem:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        conn = self.db.get_connection()
        password_hash = hashlib.md5(password.encode()).hexdigest()
        
        query = """
            SELECT u.id, u.username, u.role, u.company_id, u.full_name, u.email,
                   c.name as company_name, c.industry, c.employee_count, c.founded_date
            FROM users u
            JOIN companies c ON u.company_id = c.id
            WHERE u.username = ? AND u.password_hash = ?
        """
        
        result = pd.read_sql_query(query, conn, params=(username, password_hash))
        
        if len(result) > 0:
            # Update last login
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", 
                          (result.iloc[0]['id'],))
            conn.commit()
            
            user_data = result.iloc[0].to_dict()
            conn.close()
            return user_data
        
        conn.close()
        return None

# api_clients.py - API Client Wrappers
import os
import requests
from typing import List, Dict

class PlaidClient:
    def __init__(self):
        self.client_id = os.getenv('PLAID_CLIENT_ID')
        self.secret = os.getenv('PLAID_SECRET')
        self.env = os.getenv('PLAID_ENV', 'sandbox')
        self.connected = bool(self.client_id and self.secret)
    
    def is_connected(self) -> bool:
        return self.connected

class QuickBooksClient:
    def __init__(self):
        self.client_id = os.getenv('QB_CLIENT_ID')
        self.client_secret = os.getenv('QB_CLIENT_SECRET')
        self.connected = bool(self.client_id and self.client_secret)
    
    def is_connected(self) -> bool:
        return self.connected

class DeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"
    
    def analyze_financial_data(self, query: str, context_data: Dict) -> str:
        """Analyze financial data with AI"""
        if not self.api_key or self.api_key == 'demo_key':
            return self.fallback_analysis(query, context_data)
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": "You are an expert AI CFO. Provide specific, actionable financial insights."
                    },
                    {
                        "role": "user", 
                        "content": f"Financial data: {context_data}\n\nQuestion: {query}"
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 800
            }
            
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return self.fallback_analysis(query, context_data)
                
        except Exception as e:
            return self.fallback_analysis(query, context_data)
    
    def fallback_analysis(self, query: str, context_data: Dict) -> str:
        """Fallback analysis when AI is not available"""
        query_lower = query.lower()
        company_name = context_data.get('company_name', 'your company')
        
        if "cash" in query_lower:
            cash = context_data.get('current_cash', 0)
            runway = context_data.get('runway_days', 0)
            
            return f"""**Cash Analysis for {company_name}:**
- Current cash position: ${cash:,.0f}
- Cash runway: {runway} days
- Status: {"✅ Healthy" if runway > 90 else "⚠️ Monitor closely" if runway > 30 else "🚨 Critical"}

**Recommendations:**
1. {"Maintain current burn rate" if runway > 90 else "Reduce expenses immediately" if runway < 60 else "Secure funding urgently"}
2. Focus on collecting overdue receivables
3. Optimize payment timing with vendors"""
        
        elif "health" in query_lower:
            return f"""**Financial Health Assessment for {company_name}:**

**Strengths:**
- Regular revenue streams
- Manageable expense levels
- Good banking relationships

**Areas for Improvement:**
- AR collection processes
- Cash flow forecasting
- Expense categorization

**Key Recommendations:**
1. Implement monthly financial reviews
2. Automate invoice follow-ups
3. Create 13-week cash flow projections"""
        
        else:
            return f"""**Financial Analysis for {company_name}:**

I can help you with:
- Cash flow and runway analysis
- Accounts receivable optimization
- Expense management strategies
- Financial health assessments

Please ask specific questions like:
- "What's my cash runway?"
- "How can I improve collections?"
- "What expenses should I cut?"
- "Is my company financially healthy?"

I'll provide detailed analysis based on your actual financial data."""

# agents.py - AI Agents
from datetime import datetime, timedelta
from typing import List, Dict
import random

class CashFlowAgent:
    def __init__(self, db, plaid_client, qb_client, ai_client):
        self.db = db
        self.plaid = plaid_client
        self.qb = qb_client
        self.ai = ai_client
    
    def get_financial_summary(self, company_id: int) -> Dict:
        """Get financial summary for company"""
        # Get cash from bank accounts
        accounts = self.db.get_accounts(company_id)
        current_cash = sum(acc['current_balance'] for acc in accounts 
                          if acc['type'] in ['depository'])
        
        # Get recent transactions for burn calculation
        transactions = self.db.get_transactions(company_id, days=30)
        monthly_expenses = sum(abs(tx['amount']) for tx in transactions if tx['amount'] < 0)
        monthly_income = sum(tx['amount'] for tx in transactions if tx['amount'] > 0)
        
        # Calculate runway
        runway_days = int(current_cash / (monthly_expenses / 30)) if monthly_expenses > 0 else 999
        
        # Get AR/AP
        invoices = self.db.get_invoices(company_id)
        bills = self.db.get_bills(company_id)
        
        outstanding_ar = sum(inv['balance'] for inv in invoices if inv['balance'] > 0)
        upcoming_ap = sum(bill['balance'] for bill in bills if bill['balance'] > 0)
        
        return {
            'current_cash': current_cash,
            'monthly_burn': monthly_expenses,
            'monthly_income': monthly_income,
            'runway_days': runway_days,
            'outstanding_ar': outstanding_ar,
            'upcoming_ap': upcoming_ap
        }
    
    def get_cash_flow_chart_data(self, company_id: int) -> List[Dict]:
        """Get cash flow chart data"""
        # Get transactions grouped by date
        transactions = self.db.get_transactions(company_id, days=30)
        
        # Group by date
        daily_data = {}
        for tx in transactions:
            date = tx['date']
            if date not in daily_data:
                daily_data[date] = 0
            daily_data[date] += tx['amount']
        
        # Calculate running balance
        accounts = self.db.get_accounts(company_id)
        current_cash = sum(acc['current_balance'] for acc in accounts 
                          if acc['type'] in ['depository'])
        
        chart_data = []
        running_balance = current_cash
        
        # Sort dates and calculate running balance backwards
        sorted_dates = sorted(daily_data.keys(), reverse=True)
        for date in sorted_dates:
            chart_data.append({
                'date': date,
                'balance': running_balance,
                'daily_change': daily_data[date]
            })
            running_balance -= daily_data[date]
        
        return sorted(chart_data, key=lambda x: x['date'])
    
    def get_expense_breakdown(self, company_id: int) -> List[Dict]:
        """Get expense breakdown by category"""
        transactions = self.db.get_transactions(company_id, days=30, tx_type="Expenses")
        
        # Group by category
        category_totals = {}
        for tx in transactions:
            category = tx.get('category', 'Other').split(',')[0]  # Take first category
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += abs(tx['amount'])
        
        # Return sorted by amount
        breakdown = [{'category': cat, 'amount': amt} 
                    for cat, amt in category_totals.items()]
        return sorted(breakdown, key=lambda x: x['amount'], reverse=True)[:8]  # Top 8
    
    def generate_cash_flow_projection(self, company_id: int) -> List[Dict]:
        """Generate 13-week cash flow projection"""
        financial_data = self.get_financial_summary(company_id)
        
        current_cash = financial_data['current_cash']
        weekly_burn = financial_data['monthly_burn'] / 4.33
        weekly_income = financial_data['monthly_income'] / 4.33
        
        projection = []
        projected_cash = current_cash
        
        for week in range(14):  # 0-13 weeks
            # Add some variance for realism
            income_variance = weekly_income * random.uniform(0.8, 1.2) if week > 0 else 0
            expense_variance = weekly_burn * random.uniform(0.9, 1.1) if week > 0 else 0
            
            if week > 0:
                projected_cash = projected_cash + income_variance - expense_variance
                projected_cash = max(0, projected_cash)  # Don't go negative
            
            projection.append({
                'week': week,
                'projected_cash': projected_cash,
                'weekly_income': income_variance if week > 0 else 0,
                'weekly_expenses': expense_variance if week > 0 else 0
            })
        
        return projection
    
    def get_ai_insights(self, company_id: int, company_name: str, 
                       user_question: str = None) -> str:
        """Get AI-powered financial insights"""
        
        # Get comprehensive financial data
        financial_data = self.get_financial_summary(company_id)
        financial_data['company_name'] = company_name
        
        if not user_question:
            user_question = "Provide a financial health assessment and key recommendations"
        
        return self.ai.analyze_financial_data(user_question, financial_data)