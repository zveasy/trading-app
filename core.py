# core.py
import ibapi.client as ibclient
import ibapi.wrapper as ibwrapper
import threading

class TradingApp(ibwrapper.EWrapper, ibclient.EClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        ibwrapper.EWrapper.__init__(self)
        ibclient.EClient.__init__(self, wrapper=self)
        self.host = host
        self.port = port
        self.clientId = clientId
        self.nextOrderId = None
        self.connected_event = threading.Event()

    def nextValidId(self, orderId):
        self.nextOrderId = orderId
        self.connected_event.set()
        print(f"✅ Connected. Next valid order ID: {orderId}")

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error ({errorCode}): {errorString}")

    def start(self):
        self.connect(self.host, self.port, self.clientId)
        threading.Thread(target=self.run, daemon=True).start()
        self.connected_event.wait(timeout=10)
