# core.py (Interactive Brokers Trade Execution Only)
import threading
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from contracts import create_contract
from orders import create_order
from accounts import get_account, get_all_accounts
from utils import setup_logger

logger = setup_logger()

class TradingApp(EWrapper, EClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.nextOrderId = None
        self.connected_event = threading.Event()
        self.connect(host, port, clientId)
        threading.Thread(target=self.run, daemon=True).start()
        self.connected_event.wait(timeout=10)

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected_event.set()
        logger.info(f"✅ Connected. Next valid order ID: {orderId}")

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            logger.error(f"❌ Error ({errorCode}): {errorString}")

    def place_trade(self, symbol, quantity, action, order_type, account):
        contract = create_contract(symbol)
        order = create_order(action, order_type, quantity, account=account)
        self.placeOrder(self.nextOrderId, contract, order)
        self.nextOrderId += 1
        time.sleep(1)

def run_trade(symbol, quantity, action="BUY", order_type="MKT", account_name=None, all_accounts=False):
    app = TradingApp(clientId=10)

    if all_accounts:
        accounts_to_trade = get_all_accounts()
    elif account_name:
        acct_id = get_account(account_name)
        accounts_to_trade = [acct_id] if acct_id else []
    else:
        logger.error("❌ Specify account_name or all_accounts=True.")
        return

    for account in accounts_to_trade:
        logger.info(f"🛒 {action} {quantity} {symbol} in {account}...")
        app.place_trade(symbol, quantity, action, order_type, account)

    time.sleep(3)
    app.disconnect()
    logger.info("🔌 Disconnected.")

if __name__ == "__main__":
    run_trade("AAPL", quantity=1, all_accounts=True)
