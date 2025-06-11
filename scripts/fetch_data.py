import time
from scripts.wrapper import IBWrapper
from ib.client import IBClient
from scripts.contracts import stock, future, option  # Optional: extend to ETF, bond, commodity
import pandas as pd

class IBApp(IBWrapper, IBClient):
    def __init__(self, ip="127.0.0.1", port=7497, client_id=1):
        IBWrapper.__init__(self)
        IBClient.__init__(self, wrapper=self)
        self.connect(ip, port, client_id)
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        setattr(self, "thread", thread)

    def shutdown(self):
        self.disconnect()
        self.thread.join()

if __name__ == "__main__":
    import threading

    # ✅ Initialize app
    app = IBApp()

    # ✅ Define a contract — use stock, future, option, etc.
    aapl_contract = stock("AAPL", "SMART", "USD")

    # ✅ Fetch historical data
    df = app.get_historical_data(
        request_id=1001,
        contract=aapl_contract,
        duration="1 D",        # 1 Day
        bar_size="5 mins"      # 5-minute intervals
    )

    # ✅ Show result
    print("\n📊 Historical Data for AAPL:\n")
    print(df)

    # ✅ Clean exit
    app.shutdown()
