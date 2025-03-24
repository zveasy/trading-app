# stream_live_data.py
import threading
import time
from dataclasses import dataclass, field
import pandas as pd

# IB API Imports
from ibapi.client import EClient
from ibapi.wrapper import EWrapper

# Your existing modules
from contracts import stock, future, option, create_contract
from wrapper import IBWrapper
from client import IBClient
from utils import setup_logger

logger = setup_logger()

@dataclass
class Tick:
    time: int
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    timestamp_: pd.Timestamp = field(init=False)

    def __post_init__(self):
        self.timestamp_ = pd.to_datetime(self.time, unit="s")
        self.bid_price = float(self.bid_price)
        self.ask_price = float(self.ask_price)
        self.bid_size = int(self.bid_size)
        self.ask_size = int(self.ask_size)

class LiveDataApp(IBWrapper, IBClient):
    def __init__(self, host='127.0.0.1', port=7497, clientId=11):
        IBWrapper.__init__(self)
        IBClient.__init__(self, wrapper=self)
        self.host = host
        self.port = port
        self.clientId = clientId
        self.connect(self.host, self.port, self.clientId)
        threading.Thread(target=self.run, daemon=True).start()
        time.sleep(2)

    def get_streaming_data(self, request_id, contract):
        self.reqTickByTickData(
            reqId=request_id,
            contract=contract,
            tickType="BidAsk",
            numberOfTicks=0,
            ignoreSize=True
        )

        while True:
            if self.stream_event.is_set():
                yield Tick(*self.streaming_data[request_id])
                self.stream_event.clear()

    def stop_streaming_data(self, request_id):
        self.cancelTickByTickData(reqId=request_id)

# Example dynamic function to stream live data
def stream_live_data(symbol, secType="STK", exchange="SMART", currency="USD", contractMonth=None, strike=None, right=None):
    app = LiveDataApp()

    contract = create_contract(
        symbol=symbol,
        secType=secType,
        exchange=exchange,
        currency=currency,
        primaryExchange=None
    )

    if secType in ["FUT", "OPT"]:
        contract.lastTradeDateOrContractMonth = contractMonth
    if secType == "OPT":
        contract.strike = strike
        contract.right = right

    logger.info(f"🚀 Starting live streaming for {symbol} ({secType})...")

    try:
        for tick in app.get_streaming_data(request_id=101, contract=contract):
            print(tick)
    except KeyboardInterrupt:
        logger.info("Stopping live data stream.")
        app.stop_streaming_data(request_id=101)
        app.disconnect()
        logger.info("🔌 Disconnected.")

if __name__ == "__main__":
    # Example usage: Stream live tick data for EUR futures
    stream_live_data(symbol="EUR", secType="FUT", exchange="CME", contractMonth="202312")
