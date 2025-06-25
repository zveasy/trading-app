# tests/test_core_chaos.py
import pytest, random, time
from scripts.core import TradingApp

def _seed_ids(app, base):
    app._next_order_id = base

def chaos_connect(self, host, port, clientId):
    # 10% chance of immediate connect fail
    if random.random() < 0.1:
        raise ConnectionRefusedError("ChaosMonkey: connect failed!")
    self._connected_evt.set()

def chaos_placeOrder(self, oid, contract, order):
    # 20% chance of mid-send connection reset
    if random.random() < 0.2:
        raise ConnectionResetError("ChaosMonkey: connection dropped mid-send!")
    # 10% chance of partial fill
    if random.random() < 0.1:
        self.order_statuses[oid] = {"status": "PartiallyFilled", "filled": 1, "remaining": order.totalQuantity - 1, "avgFillPrice": 100}
    return super(type(self), self).placeOrder(oid, contract, order)

@pytest.mark.parametrize("attempt", range(25))  # many runs to catch randomness
def test_chaos_failures(monkeypatch, attempt):
    monkeypatch.setattr(TradingApp, "connect", chaos_connect)
    monkeypatch.setattr(TradingApp, "placeOrder", chaos_placeOrder)
    app = TradingApp(host="localhost", port=7497)
    _seed_ids(app, 10000)
    contract = object()
    order = type("Order", (), {"totalQuantity": 2})()
    try:
        oid = app.send_order(contract, order)
        # If we get here, system survived chaos!
    except (ConnectionRefusedError, ConnectionResetError):
        pass  # Expected sometimes, that's the chaos
