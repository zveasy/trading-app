# accounts.py
ACCOUNTS = {
    "personal": "DFH148809",
    "low_risk": "DUYYYYYY",
    "medium_risk": "DUZZZZZZ",
    "high_risk": "DUAAAAAA",
    "growth": "DUBBBBBB",
    "income": "DUCCCCCC",
}

def get_account(account_name):
    return ACCOUNTS.get(account_name)

def get_all_accounts():
    return list(ACCOUNTS.values())
