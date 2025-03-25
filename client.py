# client.py
from ibapi.client import EClient

class IBClient(EClient):
    def __init__(self, wrapper):
        super().__init__(wrapper)

    def send_order(self, contract, order):
        order_id = self.wrapper.nextValidOrderId
        self.placeOrder(orderId=order_id, contract=contract, order=order)
        self.reqIds(-1)  # Request next ID
        return order_id

    def request_positions(self):
        self.reqPositions()

    def request_portfolio(self):
        self.reqAccountUpdates(True, "")
