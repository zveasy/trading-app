from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

class FundsApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.summary = {}
        self.done = threading.Event()

    def accountSummary(self, reqId, account, tag, value, currency):
        if tag in ["NetLiquidation", "AvailableFunds", "BuyingPower", "CashBalance", "ExcessLiquidity"]:
            self.summary[tag] = f"{value} {currency}"

    def accountSummaryEnd(self, reqId):
        print("\n📊 Account Summary:")
        for tag, value in self.summary.items():
            print(f"{tag:17}: {value}")
        print("\n✅ Done retrieving account summary.")
        self.done.set()

    def error(self, reqId, errorCode, errorString):
        if errorCode not in [2104, 2106, 2158]:
            print(f"❌ Error {errorCode}: {errorString}")

def run_loop(app):
    app.run()

def main():
    app = FundsApp()
    app.connect("127.0.0.1", 7497, clientId=0)

    # Start API event loop in a separate thread
    api_thread = threading.Thread(target=run_loop, args=(app,), daemon=True)
    api_thread.start()

    time.sleep(1)  # Ensure connection is established
    app.reqAccountSummary(9001, "All", "NetLiquidation,AvailableFunds,BuyingPower,CashBalance,ExcessLiquidity")

    # Wait for response or timeout after 10 sec
    if not app.done.wait(timeout=10):
        print("⚠️ Timed out waiting for account summary.")
    
    app.disconnect()
    time.sleep(1)  # Allow disconnection cleanly

if __name__ == "__main__":
    main()



# This script connects to the Interactive Brokers API and retrieves account summary information such as Net Liquidation, Available Funds, Buying Power, Cash Balance, and Excess Liquidity.

# Response: The script uses the `ibapi` library to create a client that connects to the IB API, requests account summary data, and prints it out. It handles errors and ensures that the connection is cleanly closed after retrieving the data. The use of threading allows the API event loop to run concurrently with the main program flow, enabling a responsive application.

# (quant) (base) omnisceo@Mac trading-app % python check_funds.py 

# 📊 Account Summary:
# AvailableFunds   : 1005483.40 USD
# BuyingPower      : 4021933.60 USD
# ExcessLiquidity  : 1005483.40 USD
# NetLiquidation   : 1007494.41 USD

# ✅ Done retrieving account summary.
# (quant) (base) omnisceo@Mac trading-app % 
