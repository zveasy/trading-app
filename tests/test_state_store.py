import asyncio
from deepdiff import DeepDiff
import pytest

from scripts.state_store import StateStore

def test_load_and_upsert(tmp_path):
    db = tmp_path / "state.db"
    store = StateStore(db)
    assert store.load() == {}
    store.upsert(10001, "AAPL", 42)
    store.upsert(10002, "MSFT", 99)
    assert store.load() == {(10001,"AAPL"):42, (10002,"MSFT"):99}

def test_replace_existing(tmp_path):
    db = tmp_path / "state.db"
    store = StateStore(db)
    store.upsert(10001, "AAPL", 42)
    store.upsert(10001, "AAPL", 43)
    assert store.load() == {(10001,"AAPL"):43}


class DummyApp:
    def __init__(self):
        self.positions = [
            {"account": "DU1", "symbol": "AAPL", "position": 10, "avg_cost": 150.0},
            {"account": "DU1", "symbol": "MSFT", "position": 5, "avg_cost": 250.0},
        ]
        self.order_statuses = {
            1: {"status": "Submitted", "filled": 0, "remaining": 10, "avgFillPrice": 0.0}
        }
        self.portfolio = []

    def request_positions(self):
        pass

    def request_portfolio(self):
        pass


@pytest.mark.asyncio
async def test_snapshot_restart(tmp_path):
    db = tmp_path / "state.duckdb"
    store = StateStore(db)
    app = DummyApp()
    # Spin up the background task and allow a single snapshot to be written
    task = asyncio.create_task(store.periodic_snapshot(app, interval_s=0.1))
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    snap = store.load_last_snapshot()

    got = snap.positions.drop(columns=["snapshot_ts"]).to_dict("records")
    expected = app.positions
    assert DeepDiff(expected, got, ignore_order=True) == {}
