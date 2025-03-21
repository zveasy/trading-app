from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.order_state import OrderState
import threading
import time

class OrderCheckApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)
        self.done = threading.Event()

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState):
        print("\n🔍 Open Order Details:")
        print(f"  Order ID       : {orderId}")
        print(f"  Symbol         : {contract.symbol}")
        print(f"  Order Type     : {order.orderType}")
        print(f"  Action         : {order.action}")
        print(f"  Quantity       : {order.totalQuantity}")
        print(f"  Order Status   : {orderState.status}")
        print(f"  Avg Fill Price : {orderState.avgFillPrice}")

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, *args):
        print(f"📦 Order Status - ID: {orderId}, Status: {status}, Filled: {filled}, Remaining: {remaining}, Avg Fill Price: {avgFillPrice}")

    def openOrderEnd(self):
        print("\n✅ Finished receiving open orders.")
        self.done.set()

    def error(self, reqId, errorCode, errorString):
        if errorCode != 2104:  # Skip common connection status messages
            print(f"❌ Error {errorCode}: {errorString}")

def run_check_orders():
    app = OrderCheckApp()
    app.connect("127.0.0.1", 7497, clientId=1)

    # Start networking loop in background
    thread = threading.Thread(target=app.run)
    thread.start()

    # Request open orders
    app.reqOpenOrders()

    # Wait max 5 seconds for response
    if not app.done.wait(timeout=5):
        print("\n⚠️ Timed out waiting for open orders.")

    app.disconnect()

if __name__ == "__main__":
    run_check_orders()
