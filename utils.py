import pandas as pd
from dataclasses import dataclass, field
import logging

TRADE_BAR_PROPERTIES = ["time", "open", "high", "low", "close", "volume"]

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

def setup_logger():
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s]: %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)
