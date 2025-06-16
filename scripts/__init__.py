# trading-app/scripts/__init__.py
"""
scripts package: helper utilities (contracts, orders, accounts…)
Keep this file minimal to avoid circular-import issues.
"""
# Nothing else here
from scripts.wrapper import IBWrapper         # keep
from scripts.contracts import create_contract # <-- import directly
from scripts.orders import create_order       # <-- import directly
from scripts.accounts import get_account, get_all_accounts
from utils.utils import setup_logger



