import asyncio
import contextlib
import sys
import threading
import time
import types

import pytest
import zmq
import zmq.asyncio

from shared_proto.market_data_pb2 import MarketTick

# Synthetic tick sequence published by the fake IB client
TICKS = [
    {
        "bid_price": 101.0,
        "ask_price": 101.1,
        "last_price": 101.05,
        "bid_size": 10,
        "ask_size": 11,
        "last_size": 12,
    },
    {
        "bid_price": 102.0,
        "ask_price": 102.1,
        "last_price": 102.05,
        "bid_size": 20,
        "ask_size": 21,
        "last_size": 22,
    },
    {
        "bid_price": 103.0,
        "ask_price": 103.1,
        "last_price": 103.05,
        "bid_size": 30,
        "ask_size": 31,
        "last_size": 32,
    },
]


@pytest.fixture
def publisher(monkeypatch):
    """Return the patched market_data_publisher module."""
    import importlib
    from types import SimpleNamespace

    class FakeTicker:
        def __init__(self, contract):
            self.contract = contract
            class _Event(list):
                def __iadd__(self, func):
                    self.append(func)
                    return self
            self.updateEvent = _Event()
            self.bid = self.ask = self.last = 0.0
            self.bidSize = self.askSize = self.lastSize = 0
            self.marketCenter = "TEST"

    class FakeIB:
        def connect(self, *a, **k):
            pass

        def disconnect(self):
            pass

        def qualifyContracts(self, *a, **k):
            pass

        def reqMktData(self, contract, *a):
            ticker = FakeTicker(contract)

            def emit():
                for vals in TICKS:
                    time.sleep(0.01)
                    ticker.bid = vals["bid_price"]
                    ticker.ask = vals["ask_price"]
                    ticker.last = vals["last_price"]
                    ticker.bidSize = vals["bid_size"]
                    ticker.askSize = vals["ask_size"]
                    ticker.lastSize = vals["last_size"]
                    for cb in list(ticker.updateEvent):
                        cb(ticker)

            threading.Thread(target=emit, daemon=True).start()
            return ticker

        def sleep(self, t):
            time.sleep(t)

        def cancelMktData(self, *a, **k):
            pass

    fake_mod = types.ModuleType("ib_insync")
    fake_mod.IB = FakeIB
    fake_mod.Stock = lambda sym, exch, cur: SimpleNamespace(symbol=sym)
    sys.modules["ib_insync"] = fake_mod

    mdp = importlib.import_module("scripts.market_data_publisher")

    monkeypatch.setattr(mdp, "IB", lambda: FakeIB())
    monkeypatch.setattr(mdp, "start_http_server", lambda *a, **k: None)
    monkeypatch.setattr(mdp.signal, "signal", lambda *a, **k: None)

    class DummyMetric:
        def inc(self, *_):
            pass

        def observe(self, *_):
            pass

    monkeypatch.setattr(mdp, "ticks_total", DummyMetric())
    monkeypatch.setattr(mdp, "tick_latency_ms", DummyMetric())

    mdp._SHUTDOWN = False
    return mdp


@contextlib.contextmanager
def run_publisher(mdp):
    """Run market_data_publisher.main() in a background thread."""
    argv = sys.argv
    sys.argv = [
        "market_data_publisher",
        "--symbols",
        "AAPL",
        "--zmq-addr",
        "inproc://test",
    ]
    thread = threading.Thread(target=mdp.main, daemon=True)
    thread.start()
    try:
        yield
    finally:
        mdp._SHUTDOWN = True
        thread.join(timeout=2)
        sys.argv = argv


@pytest.mark.asyncio
async def test_market_tick_flow(publisher):
    mdp = publisher
    loop = asyncio.get_running_loop()
    ctx = zmq.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect("inproc://test")
    sub.setsockopt(zmq.SUBSCRIBE, b"market_ticks")

    received = []
    with run_publisher(mdp):
        for expected in TICKS:
            start = time.perf_counter()
            topic, payload = await asyncio.wait_for(
                loop.run_in_executor(None, sub.recv_multipart), timeout=0.05
            )
            elapsed = time.perf_counter() - start
            assert elapsed <= 0.05
            assert topic == b"market_ticks"
            msg = MarketTick()
            msg.ParseFromString(payload)
            received.append(msg)

    sub.close()
    ctx.term()

    assert len(received) >= 3
    for msg, vals in zip(received[:3], TICKS):
        assert msg.symbol == "AAPL"
        assert msg.bid_price == vals["bid_price"]
        assert msg.ask_price == vals["ask_price"]
        assert msg.last_price == vals["last_price"]
        assert msg.bid_size == vals["bid_size"]
        assert msg.ask_size == vals["ask_size"]
        assert msg.last_size == vals["last_size"]
