import asyncio
import pytest

from scripts.state_store import StateStore, SnapshotStruct

class DummyApp:
    def __init__(self):
        self.order_statuses = {1: {"status": "Submitted", "filled": 0, "remaining": 10, "avgFillPrice": 0.0}}
        self.positions = [
            {"account": "DU1", "symbol": "AAPL", "position": 10, "avg_cost": 150.0}
        ]
        self.portfolio = [
            {
                "symbol": "AAPL",
                "position": 10,
                "market_price": 152.0,
                "market_value": 1520.0,
                "average_cost": 150.0,
                "unrealized_pnl": 20.0,
                "realized_pnl": 0.0,
            }
        ]

    def request_positions(self):
        pass

    def request_portfolio(self):
        pass

@pytest.mark.asyncio
async def test_snapshot_roundtrip(tmp_path):
    db = tmp_path / "state.duckdb"
    store = StateStore(db)
    app = DummyApp()
    task = asyncio.create_task(store.periodic_snapshot(app, interval_s=0.1))
    await asyncio.sleep(0.15)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    snap = store.load_last_snapshot()
    assert isinstance(snap, SnapshotStruct)
    assert not snap.positions.empty
    assert not snap.orders.empty
    assert not snap.pnl.empty
    assert snap.positions.iloc[0]["symbol"] == "AAPL"
    assert snap.orders.iloc[0]["order_id"] == 1
