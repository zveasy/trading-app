# core.py (Interactive Brokers Trade Execution + Order Management + Portfolio + Position Inspection)
import threading
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.order import Order
from ib.client import IBClient
from scripts.contracts import create_contract
from scripts.orders import create_order
from scripts.accounts import get_account, get_all_accounts   # <--- if accounts.py is in scripts
from utils.utils import setup_logger
from scripts.wrapper import IBWrapper


logger = setup_logger()

class TradingApp(IBWrapper, IBClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=1, account=None):
        self.account = account  # <-- Add this line
        IBWrapper.__init__(self)
        IBClient.__init__(self, wrapper=self)
        self.connected_event = threading.Event()
        self.connect(host, port, clientId)
        threading.Thread(target=self.run, daemon=True).start()
        self.connected_event.wait(timeout=10)


    def send_order(self, contract, order):
        order_id = self.nextOrderId
        if self.account:
            order.account = self.account  # ✅ Assign the account here
        self.placeOrder(orderId=order_id, contract=contract, order=order)
        self.nextOrderId += 1
        return order_id


    def request_positions(self):
        self.positions = {}
        self.reqAccountUpdates(True, self.account)
        time.sleep(2)
        return self.positions

    def request_portfolio(self):
        self.portfolio = {}
        self.reqAccountUpdates(True, self.account)
        time.sleep(2)
        return self.account_values

    def cancel_all_orders(self):
        self.reqGlobalCancel()

    def cancel_order_by_id(self, order_id):
        self.cancelOrder(order_id)

    def update_order(self, contract, order, order_id):
        self.cancel_order_by_id(order_id)
        return self.send_order(contract, order)

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected_event.set()
        logger.info(f"✅ Connected. Next valid order ID: {orderId}")

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            logger.error(f"❌ Error ({errorCode}): {errorString}")

    def create_order(action, order_type, quantity, limit_price=None, account=None):
        o = Order()
        o.action        = action    # 'BUY'/'SELL'
        o.orderType     = order_type  # 'LMT', 'MKT', etc.
        o.totalQuantity = quantity
        if limit_price is not None:
            o.lmtPrice = limit_price
        if account:
            o.account = account
        o.tif = "DAY"
        return o

def run_trade(symbol, quantity, action="BUY", order_type="MKT", account_name=None, all_accounts=False):
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

        app = TradingApp(clientId=10, account=account)  # ✅ pass account here
        contract = create_contract(symbol)
        order = create_order(action, order_type, quantity, account=account)  # already sets it here
        app.send_order(contract, order)

        logger.info("📊 Fetching portfolio data...")
        portfolio = app.request_portfolio()
        print("Net Liquidation:", portfolio.get("NetLiquidation"))

        logger.info("📈 Fetching position data...")
        positions = app.request_positions()
        for symbol, pos in positions.items():
            print(f"{symbol} -> Position: {pos['position']}, Market Price: {pos['market_price']}, PnL: {pos['unrealized_pnl']}")

        app.disconnect()
        logger.info("🔌 Disconnected.")


    time.sleep(3)

    logger.info("📊 Fetching portfolio data...")
    portfolio = app.request_portfolio()
    print("Net Liquidation:", portfolio.get("NetLiquidation"))

    logger.info("📈 Fetching position data...")
    positions = app.request_positions()
    for symbol, pos in positions.items():
        print(f"{symbol} -> Position: {pos['position']}, Market Price: {pos['market_price']}, PnL: {pos['unrealized_pnl']}")

    app.disconnect()
    logger.info("🔌 Disconnected.")

if __name__ == "__main__":
    run_trade("AAPL", quantity=1, all_accounts=True)
