# AI CFO MVP

Comprehensive overview of the Plaid → QuickBooks synchronization pipeline that classifies banking transactions into Invoices (income) and Bills (expenses), persists them locally, and maintains idempotent creation in QuickBooks Online (QBO).

---

## 1. Purpose & Overview

The project ingests recent banking transactions via Plaid and mirrors appropriate accounting documents in QuickBooks Online. Each Plaid transaction is:

1. Normalized and stored in the local SQLite database.
2. Classified as income (→ QuickBooks Invoice) or expense (→ QuickBooks Bill) based on sign logic.
3. Converted into an accounting document in QBO with safeguards against duplicates using a deterministic `PrivateNote` marker (`PLD:<transaction_id>`).
4. Persisted (or skipped if already existing) for downstream analytics or reporting.

This enables automated bookkeeping acceleration for an AI-driven CFO assistant.

---

## 2. Key Features

- Plaid account & transaction synchronization (last 30 days window in current implementation).
- Automatic classification of transactions into Revenue vs Expense flows.
- Creation of QuickBooks Invoices for inflows and Bills for outflows.
- Idempotent operation using `PrivateNote` values to prevent duplicate Invoice/Bill creation.
- Dynamic ensuring/creation of dependent QBO entities (Customer, Vendor, Service Item, Accounts) with duplicate name handling (QuickBooks error code `6240`).
- Graceful handling of QuickBooks query parser issues (error code `4000`).
- SQLite persistence layer with tables for transactions, invoices, bills, accounts, sync logs, and integration tokens.
- Sandbox token bootstrap (Plaid) for quick local experimentation.

---

## 3. Repository Structure (Selected Files)

```
ai_cfo.db                # SQLite database (created at runtime)
requirements.txt         # Python dependencies
main_app_simple.py       # (Optional) Streamlit or app entry (not core to sync logic)
data_sync_script.py      # Core sync orchestration logic
mock_data.py             # Mock seeding utilities for offline/demo mode
database_module.py       # DatabaseManager abstraction for persistence
```

---

## 4. High-Level Data Flow

Textual architecture (simplified):

```
Plaid API --> Transaction Objects ------------------------------+
                                                          | Normalize & Store
                                                          v
                                                  Local SQLite (transactions)
                                                          |
                                            Classification (amount sign)
                                                          |
                    +------------------- is_income? -------------------+
                    |                                             |
                Income                                        Expense
 (qb_create_invoice_from_txn)                        (qb_create_bill_from_txn)
                    |                                             |
            Ensure QBO Entities                        Ensure QBO Entities
     (Customer, Item 'Services',                 (Vendor, Expense Account)
      Accounts as needed)                               |
                    |                                             |
            QuickBooks Invoice API                  QuickBooks Bill API
                    |                                             |
                    +-------------- PrivateNote Idempotency -------------+
                                                          |
                                   Local persistence (optional / partial)
```

---

## 5. Classification Logic

Implemented in `sync_plaid_transactions` inside `data_sync_script.py`:

- Plaid provides outflows as positive numbers; code flips sign (`amount = -float(plaid_amount)`)
- After inversion:
  - Negative amount ⇒ expense ⇒ create Bill
  - Positive amount ⇒ income ⇒ create Invoice

Edge cases:

- Pending transactions are still stored but still may be processed (could be gated later).
- Previously processed transactions can be skipped by re-enabling the commented guard around `inserted`.

---

## 6. QuickBooks Integration Details

Core helpers:

- `qb_request` – REST wrapper (authorization + JSON handling).
- `qb_query` – Runs QBO SQL-like queries (callers must escape embedded value quotes only).
- `qb_find_entity_by_name` – Locates `Customer`, `Vendor`, or `Item` using correct field mapping (`DisplayName` vs `Name`).
- `_qb_safe_create` – Creates entities with duplicate-handling & suffix retry.
- `qb_ensure_customer`, `qb_ensure_vendor`, `qb_ensure_item_service` – Idempotent ensure functions.
- `ensure_qb_account` – Retrieves or creates an Account (e.g., `Sales`, `Uncategorized Expense`).
- `qb_create_invoice_from_txn` / `qb_create_bill_from_txn` – Build minimal payloads and POST to QBO.

Invoice creation essentials:

- Sets `PrivateNote = 'PLD:<transaction_id>'` for idempotency.
- Minimal line: Service item reference; amount = absolute value of transaction.

Bill creation essentials:

- Maps Plaid category → (AccountName, AccountType, AccountSubType) via `map_plaid_category_to_qb`.
- Single expense line referencing ensured expense account.

---

## 7. Idempotency & Duplicate Handling

Techniques employed:

1. Private Note Marker: Before creation, query by `PrivateNote` to short-circuit duplicates.
2. Entity Name Reuse: Lookup existing `Customer`/`Vendor`/`Item` by name.
3. Duplicate Name Error (6240): `_qb_safe_create` intercepts API error message; if existing entity not found, retries with suffixed names (`Name-1`, `Name-2`).
4. Selective Value Escaping: Avoid over-escaping entire query strings to prevent QuickBooks `QueryParserError` (code `4000`). Only embedded literal values have quotes doubled.

---

## 8. Database Persistence Layer

Implemented in `database_module.py` (not fully shown here):

- `save_transaction` – INSERT OR IGNORE semantics to avoid duplicates.
- `save_invoice`, `save_bill` – Persist created document metadata (currently commented out in the sync loop; can be re-enabled once schema verified).
- `log_sync` – Records sync events for auditability.
- Token storage for Plaid (`plaid_tokens` table) and space reserved for QuickBooks tokens (currently session-based retrieval for demo).

Suggested Improvement: Re-enable invoice/bill persistence once QuickBooks creation stabilizes; add foreign key from invoice/bill to local transaction ID.

---

## 9. Environment Variables

Required / Common:

- `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` (sandbox|development|production)
- `QB_CLIENT_ID`, `QB_CLIENT_SECRET`, `QB_CLIENT_REDIRECT_URL`
- `APP_BASE_URL` (used to derive redirect fallback)
- Optional debug: `QUICKBOOKS_DEBUG=1`

The script currently auto-creates a Plaid sandbox `public_token` then exchanges it if no stored token exists.

---

## 10. Setup & Installation

1. Clone repository.
2. Create virtual environment and install dependencies:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with required environment variables (see section 9).
4. Initialize database (first run auto-creates tables via `DatabaseManager`).
5. (Optional) Run Streamlit UI if provided: `streamlit run main_app_simple.py`

---

## 11. Running a Sync

Full company sync (accounts + transactions + optional QBO docs):

```
python data_sync_script.py sync <company_id>
```

Bulk sync all companies:

```
python data_sync_script.py sync
```

Interactive setup (lists companies, shows integration choices):

```
python data_sync_script.py setup
```

If Plaid credentials missing, mock data seeding occurs automatically.
If QuickBooks not connected (no session tokens), Invoice/Bill creation is skipped gracefully.

---

## 12. Troubleshooting

| Symptom                                            | Cause                                        | Resolution                                                                                                |
| -------------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| QuickBooks error code 6240 (Duplicate Name Exists) | Entity (Customer/Vendor/Item) already exists | Handled automatically by `_qb_safe_create`; ensure name mapping not excessively changing                  |
| QuickBooks error code 4000 (QueryParserError)      | Over-escaped or malformed query string       | Ensure only literal values are escaped; do not call `replace("'", "''")` on entire query                  |
| Transactions repeatedly creating docs              | Guard around `inserted` commented out        | Uncomment the `if not inserted: continue` block inside `sync_plaid_transactions`                          |
| Missing Invoice/Bill lines                         | Item/Account not ensured                     | Verify `qb_ensure_item_service` and `ensure_qb_account` not throwing errors (enable `QUICKBOOKS_DEBUG=1`) |
| No QuickBooks documents created                    | Missing session tokens                       | Complete OAuth flow / set tokens in `st.session_state`                                                    |
| Amount sign seems reversed                         | Sign inversion logic unexpected              | Remember: stored amount is negative for outflows, positive for inflows                                    |

Log Enhancement Tip: Add structured logging (JSON) including transaction_id, entity type, and timing.

---

## 13. Extensibility & Future Enhancements

Planned / Suggested:

- Reinstate & enforce new-transaction guard for idempotent document creation.
- Cache ensured entities within a sync pass to reduce API calls.
- Add retry/backoff for rate limiting (HTTP 429 or 503 scenarios).
- Persist QuickBooks auth tokens in DB (refresh flow) instead of session state.
- Expand Plaid → QuickBooks mapping (multi-line invoices, tax, classes, locations).
- Add unit tests for category mapping and entity ensuring.
- Provide reconciliation reports (e.g., unmatched txns, sync latency metrics).
- JournalEntry batch posting (already scaffolded) for alternative accounting approach.

---

## 14. Security Considerations

- Never commit real credentials; `.env` should be in `.gitignore`.
- Access & refresh tokens should be encrypted at rest if persisted.
- Consider rate limit & error redaction in logs (avoid dumping raw payloads in production).

---

## 15. Glossary

- Plaid Transaction ID: Unique identifier used to build `PrivateNote` for idempotency.
- PrivateNote: QBO field leveraged to guarantee one document per source transaction.
- Idempotency: Property ensuring re-running the sync does not create duplicates.

---

## 16. Quick Start (TL;DR)

```
cp .env.example .env   # create and edit with your keys
python data_sync_script.py sync 1
# Observe console for created Invoices/Bills or mock seeding messages
```

---

## 17. Support

For implementation questions, review `data_sync_script.py` sections:

- Entity helpers: search for `qb_ensure_`
- Transaction classification: search for `is_income =`
- Idempotent markers: search for `PLD:`

Open issues or extend tests before modifying core sync logic.

---

# AI CFO – Plaid ➜ QuickBooks Sync Deep Dive

> Detailed functional flow, step mapping, validation rules, API interactions, and idempotency mechanics for transforming Plaid banking data into QuickBooks Invoices and Bills.

---

## 1. End-to-End Narrative (Happy Path)

1. Caller invokes `sync_plaid_data(company_id)`.
2. A `DataSyncManager` is instantiated (bootstraps DB + Plaid + optional QuickBooks contexts).
3. Plaid access token is retrieved (or sandbox token created & exchanged if absent) via `get_company_plaid_token()` → `exchange_plaid_public_token()`.
4. Accounts fetched with Plaid `AccountsGetRequest` → each saved using `DatabaseManager.save_account()`.
5. Transactions fetched with Plaid `TransactionsGetRequest` for last 30 days.
6. For every transaction:
   - Normalize into internal dict (sign flipped so outflows become negative).
   - Persist with `save_transaction` (INSERT OR IGNORE semantics → returns inserted flag; guard currently commented out).
   - Classify: amount > 0 ⇒ Income ⇒ Invoice; amount < 0 ⇒ Expense ⇒ Bill.
   - Obtain QuickBooks session tokens via `get_company_qb_tokens()` (UI-based session state; if none, skip QBO document creation gracefully).
   - Create QBO Invoice or Bill if not already present (`PrivateNote = 'PLD:<transaction_id>'`).
   - (Optional persistence of created invoice/bill rows — code scaffold present but commented.)
7. Sync completion logged via `log_sync` table.

---

## 2. ASCII Flow Diagram

```
+------------------+         +---------------------------+
| sync_plaid_data  |         | DataSyncManager           |
| (entrypoint)     |         |  - setup_plaid()          |
+---------+--------+         |  - setup_quickbooks()     |
          |                  +------------+--------------+
          v                               |
  get_company_plaid_token  (token bootstrap)
          |                                           (optional)
          v                                             |
   Plaid Accounts API  --> normalize --> save_account --+
          |
          v
   Plaid Transactions API --> loop each txn -------------------------------------------+
          |                                                                             |
          +--> normalize/sign flip --> save_transaction --> classify amount            |
                                              |                                         |
                                              v                                         |
                                      is_income ?                                      |
                                       /      \                                        |
                                      /        \                                       |
                           qb_create_invoice   qb_create_bill                          |
                                      |                |                               |
                        ensure customer/item   ensure vendor/expense account           |
                                      |                |                               |
                                 _qb_safe_create (dedupe logic)                        |
                                      |                |                               |
                           POST Invoice (PrivateNote)  POST Bill (PrivateNote)         |
                                      \                /                               |
                                       +--------------+                                |
                                                      |                                |
                                         (optional save_invoice/bill)                  |
                                                      |                                |
                                                      +--> log_sync (completion) <-----+
```

---

## 3. Function-by-Function Breakdown

### 3.1 Orchestration

| Function                  | Responsibility                  | Key Calls                                                                                             | Idempotency Concern                             |
| ------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `sync_plaid_data`         | High-level Plaid sync entry     | `get_company_plaid_token`, `sync_plaid_accounts`, `sync_plaid_transactions`, `log_sync`               | None (delegates)                                |
| `sync_plaid_accounts`     | Pull & persist accounts         | Plaid `accounts_get`                                                                                  | Upserts by Plaid account_id                     |
| `sync_plaid_transactions` | Pull, classify, create QBO docs | Plaid `transactions_get`, `save_transaction`, `qb_create_invoice_from_txn`, `qb_create_bill_from_txn` | Uses DB duplicate suppression + QBO PrivateNote |

### 3.2 QuickBooks Entity Utilities

| Function                                                             | Purpose                               | Notes                                               |
| -------------------------------------------------------------------- | ------------------------------------- | --------------------------------------------------- |
| `qb_request`                                                         | Low-level REST (GET/POST)             | Throws on non-2xx; caller handles                   |
| `_qb_base_url`                                                       | Company-specific base URL             | Uses `realm_id`                                     |
| `qb_query`                                                           | Executes QBO SQL-like query           | IMPORTANT: No global quote doubling                 |
| `qb_find_entity_by_name`                                             | Lookup Customer/Vendor/Item           | Field map: Customer/Vendor→DisplayName, Item→Name   |
| `_qb_safe_create`                                                    | Robust create with duplicate handling | Retries name with suffix upon error 6240            |
| `qb_ensure_customer` / `qb_ensure_vendor` / `qb_ensure_item_service` | Find or create entity                 | Item ensures a Service type + Income account        |
| `ensure_qb_account`                                                  | Find or create Account                | Uses `qb_get_account_by_name` + `qb_create_account` |
| `map_plaid_category_to_qb`                                           | Category → Account mapping            | Fallback to Uncategorized                           |

### 3.3 Document Creation

| Function                     | Input                                                            | Output                               | Validation Steps                                                                                 |
| ---------------------------- | ---------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `qb_create_invoice_from_txn` | txn dict {transaction_id, amount, date, merchant_name, category} | QBO Invoice JSON (or None if exists) | 1) PrivateNote search; 2) Ensure Customer & Item; 3) Build single service line; 4) POST          |
| `qb_create_bill_from_txn`    | txn dict                                                         | QBO Bill JSON (or None)              | 1) PrivateNote search; 2) Ensure Vendor; 3) Map category→Account; 4) Build expense line; 5) POST |

### 3.4 Supporting

| Function                                                         | Responsibility                                      |
| ---------------------------------------------------------------- | --------------------------------------------------- |
| `qb_find_invoice_by_privatenote` / `qb_find_bill_by_privatenote` | Idempotent detection by PrivateNote                 |
| `qb_get_account_by_name`                                         | Query Account by exact Name (proper escaping)       |
| `qb_create_account`                                              | POST Account (with optional subtype)                |
| `get_company_qb_tokens`                                          | Retrieve session-based tokens or produce OAuth link |
| `get_company_plaid_token`                                        | Retrieve or create Plaid access token               |
| `exchange_plaid_public_token`                                    | public_token ➜ access_token exchange                |

---

## 4. Detailed Transaction Processing Steps (`sync_plaid_transactions`)

For each raw Plaid transaction:

1. Determine representation type (object vs dict) and extract core fields.
2. Convert Plaid amount: `internal_amount = -float(plaid_amount)` (outflows negative, inflows positive).
3. Join Plaid category array to comma string (if present).
4. Persist via `save_transaction`:
   - If row already exists (same `transaction_id`), SQLite INSERT OR IGNORE returns no new row (the variable `inserted` is 0/False).
   - (OPTIONAL RECOMMENDED) Re-enable guard: `if not inserted: continue` to avoid re-posting to QBO.
5. Classify: `is_income = internal_amount > 0`.
6. Fetch QuickBooks tokens; if absent skip creation.
7. Build minimal txn projection with only needed fields for QBO creation functions.
8. If income: call `qb_create_invoice_from_txn`:
   - Compose PrivateNote = `PLD:<transaction_id>`.
   - Search existing invoice; skip if found.
   - Ensure Customer (merchant_name fallback) and Service Item.
   - Build payload with single `SalesItemLineDetail`.
   - POST; parse returned `Invoice`.
9. Else (expense): call `qb_create_bill_from_txn`:
   - Compose PrivateNote; search existing bill.
   - Ensure Vendor and Expense Account (category mapping fallback to Uncategorized Expense).
   - Build payload with single `AccountBasedExpenseLineDetail`.
   - POST; parse returned `Bill`.
10. (Optional) Persist invoice/bill to DB (currently commented code blocks show intended structure).
11. Log console message indicating created document type.
12. Continue loop.
13. Return count of transactions iterated.

---

## 5. Validation & Idempotency Mechanisms

| Layer                | Mechanism                                         | Purpose                                     |
| -------------------- | ------------------------------------------------- | ------------------------------------------- |
| Database             | `INSERT OR IGNORE` on transactions                | Prevent duplicate local processing          |
| QuickBooks Query     | `qb_find_*_by_privatenote`                        | Detect prior document creation              |
| Entity Ensure        | `qb_find_entity_by_name` before `_qb_safe_create` | Avoid redundant entity recreation           |
| Duplicate Name Error | Inspect error string for `6240`                   | Retry with suffixed name or return existing |
| PrivateNote String   | Deterministic `PLD:<transaction_id>`              | One-to-one source-to-document mapping       |

Recommended Additional Validations (future):

- Hash of (amount, date, merchant) to detect materially identical duplicates when Plaid IDs change due to corrections.
- Amount threshold filters (ignore micro-amount noise if business rule requires).

---

## 6. Error Handling Strategy

| Error Type              | Source            | Current Handling                                          | Improvement Idea                                  |
| ----------------------- | ----------------- | --------------------------------------------------------- | ------------------------------------------------- |
| 4xx/5xx from QBO        | `qb_request`      | Raises Exception                                          | Wrap with structured error object + retry/backoff |
| QueryParserError (4000) | QBO query         | Mitigated by precise field escape                         | Add test harness for queries                      |
| Duplicate Name (6240)   | QBO entity create | Handled in `_qb_safe_create` with lookup + suffix retries | Persist mapping of canonical -> chosen name       |
| Missing Tokens          | Session/UI        | Silent skip of document creation                          | Emit explicit log record in `sync_log`            |
| Network Timeout         | requests          | Exception propagate                                       | Add retry with exponential backoff                |

---

## 7. External API Endpoints Used

| Purpose                     | HTTP | Endpoint Pattern                         | Notes                                   |
| --------------------------- | ---- | ---------------------------------------- | --------------------------------------- |
| QBO Query                   | GET  | `/query?query=<encoded>&minorversion=70` | SOQL-like flavor                        |
| QBO Invoice Create          | POST | `/invoice?minorversion=75`               | Minimal lines used                      |
| QBO Bill Create             | POST | `/bill?minorversion=75`                  | Expense line only                       |
| QBO Account Create          | POST | `/account?minorversion=70`               | Type + optional subtype                 |
| QBO Item Create             | POST | `/item`                                  | Service item, references Income Account |
| QBO Customer/Vendor Create  | POST | `/customer` / `/vendor`                  | Duplicate-safe via wrapper              |
| Plaid AccountsGet           | POST | `/accounts/get` (sdk)                    | Provided by Plaid SDK                   |
| Plaid TransactionsGet       | POST | `/transactions/get` (sdk)                | Start & end date window                 |
| Plaid Sandbox Public Token  | POST | `/sandbox/public_token/create`           | Bootstraps testing                      |
| Plaid Public Token Exchange | POST | `/item/public_token/exchange`            | Access token issuance                   |

---

## 8. Data Transformations

| Field          | Source (Plaid)                     | Internal                             | QuickBooks Usage                      |
| -------------- | ---------------------------------- | ------------------------------------ | ------------------------------------- |
| Amount         | Positive outflow / negative inflow | Negated for outflow (store negative) | Absolute value in Invoice/Bill line   |
| Date           | ISO / date object                  | ISO string                           | `TxnDate`                             |
| Merchant       | `merchant_name` or `name`          | `merchant_name` fallback             | Customer/Vendor DisplayName base      |
| Category       | Array of strings                   | Comma joined                         | First token → Expense account mapping |
| Transaction ID | Plaid                              | Same                                 | Embedded in PrivateNote               |

---

## 9. Re-run Behavior

| Scenario                                   | Outcome                                        |
| ------------------------------------------ | ---------------------------------------------- |
| Transaction already saved & guard disabled | QBO attempt again (relies on PrivateNote skip) |
| Transaction already saved & guard enabled  | Entire processing skipped early                |
| Invoice/Bill already exists (PrivateNote)  | Finder returns existing → creation skipped     |
| Entity pre-exists                          | Lookup returns entity; no POST                 |

Enabling the insert guard reduces API noise and accelerates sync cycles.

---

## 10. Performance Considerations

Current implementation is single-threaded and chatty with QBO for each transaction:

- Add simple in-memory caches: `customer_cache`, `vendor_cache`, `item_cache`, `account_cache` within loop scope.
- Batch JournalEntry path exists (`build_batch_journal_items`) but not integrated for invoice/bill flow.
- Potential improvement: queue creation tasks and bulk handle backoff.

---

## 11. Security & Compliance Notes

- Secrets loaded via `.env` / `st.secrets`; ensure `.env` not committed.
- Consider encrypting stored Plaid access tokens (currently plain in DB if persisted by outside code).
- Do not log raw access/refresh tokens; present code avoids printing except for demo tokens.

---

## 12. Recommended Hardening Roadmap

1. Re-enable inserted guard.
2. Introduce rate-limit aware retry wrapper (status 429/503).
3. Centralize exception taxonomy (custom `QBOError`, `PlaidError`).
4. Add structured logger (JSON) with correlation ID = transaction_id.
5. Extend category mapping coverage + configuration file.
6. Persist QBO tokens securely (refresh flow) rather than session.
7. Unit tests for: sign flip, category mapping, entity duplicate handling, query escaping.

---

## 13. Quick Reference Cheat Sheet

| Need                    | Snippet                                        |
| ----------------------- | ---------------------------------------------- |
| Ensure Customer         | `qb_ensure_customer(tokens, name)`             |
| Ensure Vendor           | `qb_ensure_vendor(tokens, name)`               |
| Ensure Service Item     | `qb_ensure_item_service(tokens, "Services")`   |
| Ensure Account          | `ensure_qb_account(tokens, "Sales", "Income")` |
| Create Invoice from Txn | `qb_create_invoice_from_txn(tokens, txn_dict)` |
| Create Bill from Txn    | `qb_create_bill_from_txn(tokens, txn_dict)`    |
| Query Existing Invoice  | `qb_find_invoice_by_privatenote(tokens, note)` |
| Query Existing Bill     | `qb_find_bill_by_privatenote(tokens, note)`    |

---

## 14. Glossary

- Idempotency: Safe to repeat without side effects.
- PrivateNote: Arbitrary text field leveraged to store stable external key.
- 6240: QBO Duplicate Name error code.
- 4000: QBO Query Parser error code.

---

## 15. FAQ

Q: Why flip the sign of Plaid amounts?  
A: To store conventional accounting perspective: outflows negative, inflows positive; simplifies classification check (`amount > 0`)

Q: Why not always trust `merchant_name`?  
A: Sometimes absent; fallback to transaction `name` ensures a usable Customer/Vendor label.

Q: How to prevent reprocessing old transactions?  
A: Re-enable the `if not inserted: continue` guard and optionally add a `LAST_SYNC_DATE` checkpoint.

---

End of document.
