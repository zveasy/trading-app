# accounts.py
ACCOUNTS = {
    "personal": "DFH148809",
    "low_risk": "DUH148810",
    "medium_risk": "DUH148811",
    "high_risk": "DUH148812",
    "growth": "DUH148813",
    "income": "DUH148814",
}

def get_account(account_name):
    return ACCOUNTS.get(account_name)

def get_all_accounts():
    return list(ACCOUNTS.values())
