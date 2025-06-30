import pandas as pd

from utils.utils import Tick, setup_logger


def test_tick_post_init():
    t = Tick(
        time=1_700_000_000, bid_price="1.2", ask_price="1.3", bid_size="5", ask_size="7"
    )
    assert t.timestamp_ == pd.to_datetime(1_700_000_000, unit="s")
    assert isinstance(t.bid_price, float) and t.bid_price == 1.2
    assert isinstance(t.ask_price, float) and t.ask_price == 1.3
    assert t.bid_size == 5
    assert t.ask_size == 7


def test_setup_logger_creates_file(tmp_path):
    log_file = tmp_path / "test.log"
    logger = setup_logger("TestLogger", log_file=str(log_file))
    logger.info("hello")
    assert log_file.exists() and log_file.stat().st_size > 0
