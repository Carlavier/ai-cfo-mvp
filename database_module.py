# database.py - Database Manager
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import hashlib
from typing import List, Dict, Optional


class DatabaseManager:
    def __init__(self, db_path="ai_cfo.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def init_database(self):
        """Initialize database with core tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Companies table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                industry TEXT,
                employee_count INTEGER,
                founded_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Users table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                role TEXT NOT NULL,
                company_id INTEGER,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )

        # Bank accounts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                plaid_account_id TEXT,
                name TEXT NOT NULL,
                institution_name TEXT,
                type TEXT NOT NULL,
                subtype TEXT,
                current_balance REAL DEFAULT 0,
                available_balance REAL DEFAULT 0,
                mask TEXT,
                last_sync TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )

        # Transactions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                plaid_transaction_id TEXT UNIQUE,
                amount REAL NOT NULL,
                date DATE NOT NULL,
                merchant_name TEXT,
                category TEXT,
                pending BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES bank_accounts (id)
            )
        """
        )

        # Invoices table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                qb_invoice_id TEXT,
                invoice_number TEXT,
                customer_name TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                due_date DATE,
                issue_date DATE,
                status TEXT DEFAULT 'pending',
                days_overdue INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )

        # Bills table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                qb_bill_id TEXT,
                bill_number TEXT,
                vendor_name TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                due_date DATE,
                category TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )
        # Plaid tokens (store per company)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plaid_tokens (
                company_id INTEGER PRIMARY KEY,
                access_token TEXT,
                item_id TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )

        # API sync log
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                api_type TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                records_synced INTEGER DEFAULT 0,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        """
        )

        conn.commit()
        conn.close()

        # Insert demo data if empty
        self.insert_demo_data()

    def insert_demo_data(self):
        """Insert demo companies and users"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if data exists
        cursor.execute("SELECT COUNT(*) FROM companies")
        if cursor.fetchone()[0] > 0:
            conn.close()
            return

        # Insert companies
        companies = [
            ("TechStartup Inc", "Software", 25, "2022-01-15"),
            ("Retail Corp", "E-commerce", 50, "2020-06-01"),
            ("Agency Pro", "Marketing", 15, "2021-03-10"),
        ]

        for name, industry, employees, founded in companies:
            cursor.execute(
                """
                INSERT INTO companies (name, industry, employee_count, founded_date) 
                VALUES (?, ?, ?, ?)
            """,
                (name, industry, employees, founded),
            )

        # Insert users
        users = [
            ("demo_ceo", "demo123", "CEO Demo User", "ceo@demo.com", "CEO", 1),
            ("demo_cfo", "demo123", "CFO Demo User", "cfo@demo.com", "CFO", 1),
            ("demo_acc", "demo123", "Accountant Demo", "acc@demo.com", "Accountant", 1),
            ("retail_ceo", "demo123", "Retail CEO", "ceo@retail.com", "CEO", 2),
            ("agency_ceo", "demo123", "Agency CEO", "ceo@agency.com", "CEO", 3),
        ]

        for username, password, full_name, email, role, company_id in users:
            password_hash = hashlib.md5(password.encode()).hexdigest()
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, full_name, email, role, company_id) 
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (username, password_hash, full_name, email, role, company_id),
            )

        conn.commit()
        conn.close()

    def get_demo_accounts(self) -> List[Dict]:
        """Get demo accounts for login"""
        conn = self.get_connection()
        query = """
            SELECT u.username, 'demo123' as password, u.role, c.name as company_name
            FROM users u
            JOIN companies c ON u.company_id = c.id
            ORDER BY c.name, u.role
        """
        result = pd.read_sql_query(query, conn)
        conn.close()
        return result.to_dict("records")

    def get_accounts(self, company_id: int) -> List[Dict]:
        """Get bank accounts for company"""
        conn = self.get_connection()
        query = """
            SELECT * FROM bank_accounts 
            WHERE company_id = ?
            ORDER BY type, name
        """
        result = pd.read_sql_query(query, conn, params=(company_id,))
        conn.close()
        return result.to_dict("records")

    def get_recent_transactions(self, company_id: int, limit: int = 10) -> List[Dict]:
        """Get recent transactions for company"""
        conn = self.get_connection()
        query = """
            SELECT t.date, t.merchant_name, t.amount, t.category
            FROM transactions t
            JOIN bank_accounts ba ON t.account_id = ba.id
            WHERE ba.company_id = ?
            ORDER BY t.date DESC, t.id DESC
            LIMIT ?
        """
        result = pd.read_sql_query(query, conn, params=(company_id, limit))
        conn.close()
        return result.to_dict("records")

    def get_transactions(
        self,
        company_id: int,
        days: int = 30,
        min_amount: float = 0,
        tx_type: str = "All",
    ) -> List[Dict]:
        """Get filtered transactions"""
        conn = self.get_connection()

        # Base query
        query = """
            SELECT t.date, t.merchant_name, t.amount, t.category, t.pending
            FROM transactions t
            JOIN bank_accounts ba ON t.account_id = ba.id
            WHERE ba.company_id = ?
            AND t.date >= date('now', '-{} days')
        """.format(
            days
        )

        params = [company_id]

        # Add filters
        if min_amount > 0:
            query += " AND ABS(t.amount) >= ?"
            params.append(min_amount)

        if tx_type == "Income":
            query += " AND t.amount > 0"
        elif tx_type == "Expenses":
            query += " AND t.amount < 0"

        query += " ORDER BY t.date DESC"

        result = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return result.to_dict("records")

    def get_invoices(self, company_id: int) -> List[Dict]:
        """Get invoices for company"""
        conn = self.get_connection()
        query = "SELECT * FROM invoices WHERE company_id = ? ORDER BY due_date"
        result = pd.read_sql_query(query, conn, params=(company_id,))
        conn.close()
        return result.to_dict("records")

    def get_bills(self, company_id: int) -> List[Dict]:
        """Get bills for company"""
        conn = self.get_connection()
        query = "SELECT * FROM bills WHERE company_id = ? ORDER BY due_date"
        result = pd.read_sql_query(query, conn, params=(company_id,))
        conn.close()
        return result.to_dict("records")

    def get_sync_status(self, company_id: int) -> Dict:
        """Get last sync status"""
        conn = self.get_connection()

        # Get last Plaid sync
        plaid_query = """
            SELECT MAX(created_at) as last_sync
            FROM sync_log
            WHERE company_id = ? AND api_type = 'plaid' AND success = 1
        """
        plaid_result = pd.read_sql_query(plaid_query, conn, params=(company_id,))
        plaid_sync = (
            plaid_result["last_sync"].iloc[0] if len(plaid_result) > 0 else None
        )

        # Get last QB sync
        qb_query = """
            SELECT MAX(created_at) as last_sync
            FROM sync_log
            WHERE company_id = ? AND api_type = 'quickbooks' AND success = 1
        """
        qb_result = pd.read_sql_query(qb_query, conn, params=(company_id,))
        qb_sync = qb_result["last_sync"].iloc[0] if len(qb_result) > 0 else None

        conn.close()
        return {"plaid_last_sync": plaid_sync, "qb_last_sync": qb_sync}

    def save_account(self, account_data: Dict) -> int:
        """Save bank account"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO bank_accounts 
            (company_id, plaid_account_id, name, institution_name, type, subtype,
             current_balance, available_balance, mask, last_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
            (
                account_data["company_id"],
                account_data["account_id"],
                account_data["name"],
                account_data.get("institution_name", ""),
                account_data["type"],
                account_data["subtype"],
                account_data["current_balance"],
                account_data["available_balance"],
                account_data.get("mask", ""),
            ),
        )

        account_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return account_id

    def save_transaction(self, transaction_data: Dict) -> int:
        """Save transaction"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO transactions 
                (account_id, plaid_transaction_id, amount, date, merchant_name, category, pending)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    transaction_data["account_id"],
                    transaction_data["transaction_id"],
                    transaction_data["amount"],
                    transaction_data["date"],
                    transaction_data["merchant_name"],
                    transaction_data.get("category", ""),
                    transaction_data.get("pending", False),
                ),
            )

            transaction_id = cursor.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            # Transaction already exists
            transaction_id = 0

        conn.close()
        return transaction_id

    def save_invoice(self, invoice_data: Dict) -> int:
        """Save invoice"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO invoices 
            (company_id, qb_invoice_id, invoice_number, customer_name, amount, balance,
             due_date, issue_date, status, days_overdue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                invoice_data["company_id"],
                invoice_data.get("qb_invoice_id", ""),
                invoice_data["invoice_number"],
                invoice_data["customer_name"],
                invoice_data["amount"],
                invoice_data["balance"],
                invoice_data["due_date"],
                invoice_data["issue_date"],
                invoice_data["status"],
                invoice_data.get("days_overdue", 0),
            ),
        )

        invoice_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return invoice_id

    def save_bill(self, bill_data: Dict) -> int:
        """Save bill"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO bills 
            (company_id, qb_bill_id, bill_number, vendor_name, amount, balance,
             due_date, category, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                bill_data["company_id"],
                bill_data.get("qb_bill_id", ""),
                bill_data["bill_number"],
                bill_data["vendor_name"],
                bill_data["amount"],
                bill_data["balance"],
                bill_data["due_date"],
                bill_data.get("category", ""),
                bill_data["status"],
            ),
        )

        bill_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return bill_id

    def log_sync(
        self,
        company_id: int,
        api_type: str,
        sync_type: str,
        records_synced: int,
        success: bool = True,
        error_message: str = None,
    ):
        """Log API sync"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO sync_log 
            (company_id, api_type, sync_type, records_synced, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (company_id, api_type, sync_type, records_synced, success, error_message),
        )

        conn.commit()
        conn.close()

    def get_account_by_plaid_id(
        self, company_id: int, plaid_account_id: str
    ) -> Optional[Dict]:
        """Get account by Plaid ID"""
        conn = self.get_connection()
        query = """
            SELECT * FROM bank_accounts 
            WHERE company_id = ? AND plaid_account_id = ?
        """
        result = pd.read_sql_query(query, conn, params=(company_id, plaid_account_id))
        conn.close()

        if len(result) > 0:
            return result.iloc[0].to_dict()
        return None

    def set_plaid_tokens(
        self, company_id: int, access_token: str, item_id: str
    ) -> None:
        """Persist Plaid tokens for a company"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO plaid_tokens (company_id, access_token, item_id, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(company_id) DO UPDATE SET
              access_token=excluded.access_token,
              item_id=excluded.item_id,
              updated_at=CURRENT_TIMESTAMP
        """,
            (company_id, access_token, item_id),
        )
        conn.commit()
        conn.close()

    def get_plaid_tokens(self, company_id: int) -> Optional[Dict]:
        """Load Plaid tokens for a company"""
        conn = self.get_connection()
        df = pd.read_sql_query(
            "SELECT company_id, access_token, item_id, updated_at FROM plaid_tokens WHERE company_id = ?",
            conn,
            params=(company_id,),
        )
        conn.close()
        if len(df) == 0:
            return None
        return df.iloc[0].to_dict()
