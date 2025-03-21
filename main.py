from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
import time

class TradeApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print(f"Next Valid Order ID: {orderId}")

        # Define the contract
        contract = Contract()
        contract.symbol = "AAPL"
        contract.secType = "STK"
        contract.currency = "USD"
        contract.exchange = "SMART"

        # Define the order
        order = Order()
        order.action = "BUY"
        order.orderType = "MKT"
        order.totalQuantity = 10

        # 🚫 Disable unsupported attributes
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        print("Order attributes (final):", order.__dict__)

        self.placeOrder(orderId, contract, order)
        time.sleep(3)
        self.disconnect()

app = TradeApp()
app.connect("127.0.0.1", 7497, clientId=0)
app.run()
