# trading-app/scripts/__init__.py
"""
scripts package: helper utilities (contracts, orders, accounts…)
Keep this file minimal to avoid circular-import issues.
"""
from scripts.accounts import get_account, get_all_accounts
from scripts.contracts import create_contract
from scripts.orders import create_order

# Nothing else here
from scripts.wrapper import IBWrapper  # keep
from utils.utils import setup_logger

__all__ = [
    "IBWrapper",
    "create_contract",
    "create_order",
    "get_account",
    "get_all_accounts",
    "setup_logger",
]
