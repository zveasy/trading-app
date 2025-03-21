from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.execution import ExecutionFilter
import threading
import time

class ExecutionApp(EClient, EWrapper):
    def __init__(self):
        EClient.__init__(self, self)
        self.done = threading.Event()
        self.summary = []  # Track all executions

    def nextValidId(self, orderId):
        print("✅ Connected. Requesting past executions...\n")
        self.reqExecutions(10001, ExecutionFilter())  # Request all executions

    def execDetails(self, reqId, contract, execution):
        trade = {
            "symbol": contract.symbol,
            "side": execution.side,
            "shares": execution.shares,
            "price": execution.price,
            "time": execution.time
        }
        self.summary.append(trade)

        print(f"📥 Trade Execution:")
        print(f"  Symbol   : {trade['symbol']}")
        print(f"  Side     : {trade['side']}")
        print(f"  Shares   : {trade['shares']}")
        print(f"  Price    : {trade['price']}")
        print(f"  Time     : {trade['time']}\n")

    def execDetailsEnd(self, reqId):
        if not self.summary:
            print("⚠️ No past executions found.")
        else:
            print(f"✅ Done retrieving {len(self.summary)} executions.")
        self.done.set()

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error {errorCode}: {errorString}")

def run_check_executions():
    app = ExecutionApp()
    app.connect("127.0.0.1", 7497, clientId=1)

    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()

    if not app.done.wait(timeout=10):
        print("⚠️ Timed out waiting for executions.")
        app.disconnect()

if __name__ == "__main__":
    run_check_executions()
