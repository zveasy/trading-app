import threading
import time

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order 

from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.orders import create_order
from accounts import get_account, get_all_accounts
from utils.utils import setup_logger




logger = setup_logger()

def run_trade(symbol, quantity, account_name=None, all_accounts=False):
    app = TradingApp(clientId=10)  # from core.py
    app.start()

    contract = create_contract(symbol)

    accounts_to_trade = []
    if all_accounts:
        accounts_to_trade = get_all_accounts()
        logger.info(f"🚀 Trading {symbol} across ALL accounts.")
    elif account_name:
        acct_id = get_account(account_name)
        if not acct_id:
            logger.error(f"❌ Account name '{account_name}' not found.")
            return
        accounts_to_trade = [acct_id]
        logger.info(f"🚀 Trading {symbol} for account '{account_name}'.")
    else:
        logger.error("❌ You must specify either an account_name or set all_accounts=True.")
        return

    # Submit trades to each account
    for account in accounts_to_trade:
        order = create_order("BUY", "MKT", quantity, account=account)
        logger.info(f"🛒 Placing {order.action} order for {quantity} shares of {symbol} in account {account}...")
        app.placeOrder(app.nextOrderId, contract, order)
        app.nextOrderId += 1
        time.sleep(1)  # Short delay between orders to avoid throttling

    time.sleep(3)  # Allow orders to be processed
    app.disconnect()
    logger.info("🔌 Disconnected.")


if __name__ == "__main__":
    run_trade("AAPL", quantity=5, all_accounts=True)



# # Trade for ALL accounts
# run_trade("AAPL", 10, all_accounts=True)

# # Trade only personal account
# run_trade("TSLA", 2, account_name="personal")

# # Trade only high-risk portfolio
# run_trade("NVDA", 5, account_name="high_risk")
