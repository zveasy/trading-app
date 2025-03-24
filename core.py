import threading
import time

# IB API Imports
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

# Your project modules
from contracts import create_contract
from orders import create_order
from accounts import get_account, get_all_accounts
from utils import setup_logger

logger = setup_logger()

class TradingApp(EWrapper, EClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.host = host
        self.port = port
        self.clientId = clientId
        self.nextOrderId = None
        self.connected_event = threading.Event()

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected_event.set()
        logger.info(f"✅ Connected. Next valid order ID: {orderId}")

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            logger.error(f"❌ Error ({errorCode}): {errorString}")

    def start(self):
        """
        Initiates a connection to IB TWS or Gateway and spawns the event loop in a thread.
        """
        self.connect(self.host, self.port, self.clientId)
        threading.Thread(target=self.run, daemon=True).start()
        # Wait up to 10 seconds for 'nextValidId' callback
        self.connected_event.wait(timeout=10)

def run_trade(symbol, quantity, account_name=None, all_accounts=False):
    """
    A convenience function to demonstrate placing a trade
    using the TradingApp class in this same file.
    """
    app = TradingApp(clientId=10)  
    app.start()

    contract = create_contract(symbol)

    # Determine which accounts to use
    if all_accounts:
        accounts_to_trade = get_all_accounts()
        logger.info(f"🚀 Trading {symbol} across ALL accounts: {accounts_to_trade}")
    elif account_name:
        acct_id = get_account(account_name)
        if not acct_id:
            logger.error(f"❌ Account name '{account_name}' not found.")
            return
        accounts_to_trade = [acct_id]
        logger.info(f"🚀 Trading {symbol} for account '{account_name}' ({acct_id}).")
    else:
        logger.error("❌ Must specify either account_name or all_accounts=True.")
        return

    # Place orders for each account
    for account in accounts_to_trade:
        order = create_order("BUY", "MKT", quantity, account=account)
        logger.info(f"🛒 Placing {order.action} {quantity} {symbol} in {account}...")
        app.placeOrder(app.nextOrderId, contract, order)
        app.nextOrderId += 1
        time.sleep(1)  # short delay to avoid rate-limit

    time.sleep(3)  # give IB time to process
    app.disconnect()
    logger.info("🔌 Disconnected.")

if __name__ == "__main__":
    # Example usage: trade AAPL across ALL your accounts
    run_trade("AAPL", quantity=1, all_accounts=True)
