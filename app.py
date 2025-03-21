from .client import IBClient
from .wrapper import IBWrapper
import threading

class TradingApp(IBWrapper, IBClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        IBWrapper.__init__(self)
        IBClient.__init__(self, wrapper=self)
        self.host = host
        self.port = port
        self.clientId = clientId
        self.nextOrderId = None
        self.connected_event = threading.Event()

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected_event.set()
        print(f"✅ Connected. Next valid order ID: {orderId}")

    def start(self):
        self.connect(self.host, self.port, self.clientId)
        threading.Thread(target=self.run, daemon=True).start()
        self.connected_event.wait(timeout=10)
