from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class TestApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)
        self.done = threading.Event()

    def nextValidId(self, orderId):
        print("✅ Connected! Your next valid order ID:", orderId)
        self.reqPositions()  # Start fetching positions

    def position(self, account, contract, position, avgCost):
        if position != 0:
            print(f"\n📊 Position:")
            print(f"  Symbol   : {contract.symbol}")
            print(f"  Quantity : {position}")
            print(f"  Avg Cost : {avgCost}")

    def positionEnd(self):
        print("\n✅ Done retrieving positions.")
        self.done.set()
        self.disconnect()

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error {errorCode}: {errorString}")

app = TestApp()
app.connect("127.0.0.1", 7497, clientId=0)

# Run in background so we can time out or force quit
thread = threading.Thread(target=app.run)
thread.start()

# Wait until positions are received or timeout (10s max)
if not app.done.wait(timeout=10):
    print("\n⚠️ Timed out waiting for position data.")
    app.disconnect()
