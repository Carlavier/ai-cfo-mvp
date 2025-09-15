import json
import random
from datetime import datetime, timedelta

# Base config
config = {
    "seed": "my-seed-string-3",
    "override_accounts": [
        {
            "type": "depository",
            "subtype": "checking",
            "identity": {
                "names": ["John Doe"],
                "phone_numbers": [
                    {"primary": True, "type": "home", "data": "4673956022"}
                ],
                "emails": [
                    {
                        "primary": True,
                        "type": "primary",
                        "data": "accountholder0@example.com",
                    }
                ],
                "addresses": [
                    {
                        "primary": True,
                        "data": {
                            "city": "Malakoff",
                            "region": "NY",
                            "street": "2992 Cameron Road",
                            "postal_code": "14236",
                            "country": "US",
                        },
                    }
                ],
            },
            "transactions": [],
        }
    ],
}

# --- Dynamic last 30 days window ---
start_date = datetime.now() - timedelta(days=30)
end_date = datetime.now()
days_window = (end_date.date() - start_date.date()).days + 1

# Optional reproducible randomness
random.seed(config["seed"])

merchants = [
    "Netflix",
    "Amazon",
    "Spotify",
    "Walmart",
    "Apple",
    "Google",
    "Uber",
    "Lyft",
    "Target",
    "McDonald's",
]

NUM_TXNS = 100

for _ in range(NUM_TXNS):
    # Pick a random day in the window
    date_transacted = start_date + timedelta(days=random.randint(0, days_window - 1))
    # Posted date: same day or +1 / +2
    date_posted = date_transacted + timedelta(days=random.choice([0, 1, 2]))
    merchant = random.choice(merchants)
    amount = round(random.uniform(5, 200), 2)

    txn = {
        "date_transacted": date_transacted.strftime("%Y-%m-%d"),
        "date_posted": date_posted.strftime("%Y-%m-%d"),
        "currency": "USD",
        "amount": amount,
        "description": f"Purchase at {merchant}",
    }
    config["override_accounts"][0]["transactions"].append(txn)

# Sort transactions by transacted date ascending for readability
config["override_accounts"][0]["transactions"].sort(
    key=lambda x: (x["date_transacted"], x["date_posted"])
)

# Write to file
with open("plaid_sandbox_100_txn.json", "w") as f:
    json.dump(config, f, indent=2)

print(
    "✅ File plaid_sandbox_100_txn.json generated with 100 transactions (last 30 days)"
)
