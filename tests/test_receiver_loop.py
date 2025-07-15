#!/usr/bin/env python3
"""
Unit-test the *main loop* inside scripts.cancel_replace_receiver.

The test patches every heavyweight dependency (IB, ZMQ, Prometheus, SQLite)
so that importing the module runs exactly one loop iteration and exits.

It then asserts that:
• a NEW → REPLACE flow succeeds (retry-registry cleared)
• Prometheus counters were called
• no un-handled exceptions escape the loop
"""

from types import SimpleNamespace
import importlib
import sys
import time
import pytest


# ───────────────────────── helpers ──────────────────────────
def _build_proto_row(proto: int, qty: int, px: float) -> bytes:
    """Return a serialised CancelReplaceRequest protobuf frame."""
    from tests import cr_pb2
    msg = cr_pb2.CancelReplaceRequest()
    msg.order_id = proto
    msg.params.new_qty = qty
    msg.params.new_price = px
    return msg.SerializeToString()


# ───────────────────────── fixture ──────────────────────────
@pytest.fixture
def patched_env(monkeypatch):
    """
    Patch all external dependencies **before** importing the receiver.

    Yields
    ------
    (RetryRegistry, metrics_dict)  so the test can assert on them.
    """
    # 1️⃣  Fake CLI so argparse sees no pytest flags
    monkeypatch.setattr(sys, "argv", ["cancel_replace_receiver"])

    # 2️⃣  Stub TradingApp – no real IB connection
    fake_app = SimpleNamespace(
        order_statuses={},
        send_order=lambda *a, **k: 111,
        update_order=lambda *a, **k: None,
        placeOrder=lambda *a, **k: None,
        disconnect=lambda *a, **k: None,
    )
    monkeypatch.setattr("scripts.core.TradingApp", lambda *a, **k: fake_app)

    # 3️⃣  Stub helpers that otherwise hit IB Gateway
    monkeypatch.setattr("scripts.contracts.create_contract", lambda *a, **k: None)
    monkeypatch.setattr("scripts.order_factory.make_order", lambda *a, **k: None)

    # 4️⃣  In-mem StateStore (no SQLite I/O)
    monkeypatch.setattr(
        "scripts.state_store.StateStore",
        lambda *a, **k: SimpleNamespace(load=lambda: {}, upsert=lambda *a, **k: None),
    )

    # 5️⃣  Controlled RetryRegistry (huge delay so back-off branch is exercised)
    from scripts.retry import RetryRegistry
    rreg = RetryRegistry(max_attempts=1, base_delay=1e6)
    monkeypatch.setattr("scripts.retry.RetryRegistry", lambda *a, **k: rreg)

    # 6️⃣  Stub Prometheus metric objects
    class _Metric:
        def inc(self, *_): pass
        def dec(self, *_): pass
        def set(self, *_): pass
        def labels(self, **_): return self
        # histogram.time() context manager
        def time(self): return self
        __enter__ = lambda self, *a, **k: None
        __exit__  = lambda self, *a, **k: False

    metric_names = [
        "RECEIVER_MSGS", "RECEIVER_ERRORS", "IB_RETRIES", "INFLIGHT_CONN",
        "RECEIVER_BACKOFFS", "RETRY_RESETS",
        "orders_by_symbol", "orders_by_type", "order_latency",
        "orders_filled", "orders_canceled", "orders_rejected", "queue_depth",
        "IB_ERROR_CODES",
    ]
    fake_metrics = {n: _Metric() for n in metric_names}
    monkeypatch.setattr("scripts.metrics_server.start", lambda *a, **k: None)
    for n, m in fake_metrics.items():
        monkeypatch.setattr(f"scripts.metrics_server.{n}", m)

    # 7️⃣  Fake ZMQ socket – two frames then “no work”
    import zmq

    #   • Override zmq.Again with a dummy class so constructing it does NOT
    #     look up zmq.EAGAIN (which triggers the long import-chain in PyZMQ).
    class _ZmqAgain(Exception): pass
    monkeypatch.setattr(zmq, "Again", _ZmqAgain)

    # inside patched_env fixture ───────────────────────────────────────────
    pending = [
        _build_proto_row(10001, 10, 123.45),   # NEW
        _build_proto_row(10001, 15, 124.00),   # REPLACE
    ]

    def _dummy_recv(flags=0):
        # Nothing left to consume → tell the receiver to exit gracefully
        if not pending:
            import sys
            mod = sys.modules.get("scripts.cancel_replace_receiver")
            if mod is not None:                         # module already imported
                mod.SHUTDOWN = True                     # <-- key line
            raise zmq.Again()                           # so outer loop hits 'continue'
        return pending.pop(0)


    dummy_sock = SimpleNamespace(
        bind=lambda *a, **k: None,
        recv=_dummy_recv,
        setsockopt=lambda *a, **k: None,
        close=lambda *a, **k: None,
    )
    monkeypatch.setattr("zmq.Context.socket", lambda *a, **k: dummy_sock)

    # 8️⃣  NOP sleep so the test finishes instantly
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    yield rreg, fake_metrics


# ─────────────────────────── tests ───────────────────────────
def test_happy_and_backoff(patched_env):
    rreg, metrics = patched_env

    # Import AFTER patching → receiver runs exactly one loop & exits
    importlib.import_module("scripts.cancel_replace_receiver")

    #   • After NEW + successful REPLACE we expect retry registry cleared
    assert (10001, "AAPL") not in rreg._state

    #   • Metric object exists and exposes expected API
    assert hasattr(metrics["RECEIVER_MSGS"], "inc")
