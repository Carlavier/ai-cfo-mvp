"""Mock data generators for fallback when external API sync fails.

Provides helpers to seed realistic demo data into the local SQLite DB
via DatabaseManager.save_* methods.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Tuple, List, Dict

from database_module import DatabaseManager


def _rand_date(days_back: int = 30) -> str:
    offset = random.randint(0, max(0, days_back))
    d = datetime.now() - timedelta(days=offset)
    return d.strftime("%Y-%m-%d")


def seed_mock_plaid(db: DatabaseManager, company_id: int) -> Tuple[int, int]:
    """Seed mock banking accounts and transactions.

    Returns: (accounts_synced, transactions_synced)
    """
    accounts: List[Dict] = [
        {
            "company_id": company_id,
            "account_id": f"mock_acct_{company_id}_chk",
            "name": "Operating Checking",
            "institution_name": "Mock Bank",
            "type": "depository",
            "subtype": "checking",
            "current_balance": 75000.00,
            "available_balance": 74000.00,
            "mask": "1234",
        },
        {
            "company_id": company_id,
            "account_id": f"mock_acct_{company_id}_svg",
            "name": "Reserve Savings",
            "institution_name": "Mock Bank",
            "type": "depository",
            "subtype": "savings",
            "current_balance": 25000.00,
            "available_balance": 25000.00,
            "mask": "9876",
        },
    ]

    account_rows: List[int] = []
    for acct in accounts:
        account_id = db.save_account(acct)
        # save_account may return 0 on replace; fetch or fallback
        if account_id == 0:
            local = db.get_account_by_plaid_id(company_id, acct["account_id"]) or {}
            account_id = local.get("id", 0)
        account_rows.append(account_id)

    # Transactions
    merchants_income = ["Stripe Payout", "Shopify Payout", "Client Payment", "Interest"]
    merchants_exp = [
        "AWS",
        "Google Cloud",
        "Figma",
        "Slack",
        "OpenAI",
        "Payroll",
        "Office Rent",
        "Uber",
        "Restaurant",
        "Supplies",
    ]
    categories_income = ["Sales", "Services", "Interest"]
    categories_exp = [
        "Cloud Services",
        "Software",
        "Payroll",
        "Rent",
        "Travel",
        "Meals",
        "Office Supplies",
    ]

    transactions_synced = 0
    days = 30
    random.seed(company_id)

    for day in range(days):
        date_str = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")

        # 0-2 income per day
        for _ in range(random.randint(0, 2)):
            acct_idx = random.randrange(len(account_rows))
            txn = {
                "account_id": account_rows[acct_idx],
                "transaction_id": str(uuid.uuid4()),
                "amount": float(round(random.uniform(200.0, 5000.0), 2)),
                "date": date_str,
                "merchant_name": random.choice(merchants_income),
                "category": random.choice(categories_income),
                "pending": False,
            }
            if db.save_transaction(txn) > 0:
                transactions_synced += 1

        # 2-5 expenses per day
        for _ in range(random.randint(2, 5)):
            acct_idx = random.randrange(len(account_rows))
            amt = float(round(random.uniform(10.0, 3000.0), 2))
            txn = {
                "account_id": account_rows[acct_idx],
                "transaction_id": str(uuid.uuid4()),
                "amount": -amt,  # expenses negative in our schema
                "date": date_str,
                "merchant_name": random.choice(merchants_exp),
                "category": random.choice(categories_exp),
                "pending": False,
            }
            if db.save_transaction(txn) > 0:
                transactions_synced += 1

    return len(accounts), transactions_synced


def seed_mock_quickbooks(db: DatabaseManager, company_id: int) -> Tuple[int, int]:
    """Seed mock invoices and bills.

    Returns: (invoices_synced, bills_synced)
    """
    random.seed(1000 + company_id)

    # Invoices (AR)
    customers = ["Acme Co", "Globex", "Initech", "Soylent", "Umbrella"]
    invoices_synced = 0
    today = datetime.now()

    for i in range(8):
        total = float(round(random.uniform(500.0, 15000.0), 2))
        # 50% partially unpaid, 25% unpaid, 25% paid
        r = random.random()
        if r < 0.25:
            balance = total
        elif r < 0.75:
            balance = float(round(total * random.uniform(0.1, 0.9), 2))
        else:
            balance = 0.0

        issue_date = (today - timedelta(days=random.randint(0, 45))).strftime("%Y-%m-%d")
        due_date = (today + timedelta(days=random.randint(-15, 30))).strftime("%Y-%m-%d")

        # status
        if balance == 0:
            status = "paid"
            days_overdue = 0
        else:
            due_dt = datetime.strptime(due_date, "%Y-%m-%d")
            days_overdue = max(0, (today - due_dt).days)
            status = "overdue" if days_overdue > 0 else "pending"

        inv = {
            "company_id": company_id,
            "qb_invoice_id": f"mock-inv-{company_id}-{i}",
            "invoice_number": f"INV-{1000 + i}",
            "customer_name": random.choice(customers),
            "amount": total,
            "balance": balance,
            "due_date": due_date,
            "issue_date": issue_date,
            "status": status,
            "days_overdue": days_overdue,
        }
        db.save_invoice(inv)
        invoices_synced += 1

    # Bills (AP)
    vendors = ["Amazon", "GCP", "Atlas Hosting", "DesignCo", "Landlord LLC", "PayrollCo"]
    categories = ["Supplies", "Cloud", "Hosting", "Services", "Rent", "Payroll"]
    bills_synced = 0

    for i in range(10):
        amount = float(round(random.uniform(100.0, 8000.0), 2))
        r = random.random()
        if r < 0.3:
            balance = 0.0
        elif r < 0.8:
            balance = float(round(amount * random.uniform(0.2, 0.9), 2))
        else:
            balance = amount

        due_date = (today + timedelta(days=random.randint(-10, 25))).strftime("%Y-%m-%d")
        if balance == 0:
            status = "paid"
        else:
            due_dt = datetime.strptime(due_date, "%Y-%m-%d")
            status = "overdue" if due_dt < today else "pending"

        bill = {
            "company_id": company_id,
            "qb_bill_id": f"mock-bill-{company_id}-{i}",
            "bill_number": f"BILL-{2000 + i}",
            "vendor_name": random.choice(vendors),
            "amount": amount,
            "balance": balance,
            "due_date": due_date,
            "category": random.choice(categories),
            "status": status,
        }
        db.save_bill(bill)
        bills_synced += 1

    return invoices_synced, bills_synced
