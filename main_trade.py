import threading
import time

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order 

from core import TradingApp
from contracts import create_contract
from orders import create_order
from accounts import get_account, get_all_accounts
from utils import setup_logger



logger = setup_logger()

class TradeApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)
        self.next_order_id = None
        self.ready = threading.Event()

    def nextValidId(self, orderId):
        print(f"✅ Connected. Next valid order ID: {orderId}")
        self.next_order_id = orderId
        self.ready.set()

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error {errorCode}: {errorString}")

def create_contract():
    contract = Contract()
    contract.symbol = "AAPL"
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    return contract

def create_order():
    order = Order()
    order.action = "BUY"
    order.orderType = "MKT"
    order.totalQuantity = 1

    # Disable problematic attributes explicitly
    order.eTradeOnly = False
    order.firmQuoteOnly = False
    order.transmit = True

    # ✅ Explicitly set your IBKR paper-trading account ID here
    order.account = "DFH148809"  # Replace with YOUR paper account ID

    return order



def run_trade(symbol, quantity, account_name=None, all_accounts=False):
    app = TradingApp(clientId=10)  # use a distinct clientId
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
