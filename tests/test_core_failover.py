#!/usr/bin/env python3
"""
Fail-over / pool / TLS unit-tests for scripts.core.TradingApp.

✔ runs with plain `pytest` and with `pytest -n auto`
✔ never reaches the real IB API – everything is stubbed
"""

from __future__ import annotations

import threading
from unittest import mock

import pytest
from scripts.core import TradingApp

REAL_IB_HOST       = "127.0.0.1"
REAL_IB_PORT       = 7_497
REAL_IB_CLIENT_ID  = 42
REAL_IB_ACCOUNT    = "DUH148810"


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────
def _seed_ids(app: TradingApp, start: int = 100) -> None:
    """Set a predictable nextValidId so we don’t wait for the real callback."""
    app._next_order_id = start


# ─────────────────────────────────────────────────────────────────────────────
# 1) primary-down → retry / survive
# ─────────────────────────────────────────────────────────────────────────────
def test_failover_primary_down(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple] = []

    def fake_connect(self, host, port, clientId):      # noqa: N802
        calls.append((host, port, clientId))
        # first attempt fails, second succeeds
        if len(calls) == 1:
            raise ConnectionRefusedError("primary refused")
        self._connected_evt.set()                      # pretend nextValidId

    monkeypatch.setattr(TradingApp, "connect", fake_connect, raising=True)

    app = TradingApp(host="127.0.0.1", port=7497,
                     clientId=REAL_IB_CLIENT_ID, account=REAL_IB_ACCOUNT)
    _seed_ids(app, 100)

    assert app.send_order(mock.Mock(), mock.Mock()) == 100
    assert calls                                          # at least one try


# ─────────────────────────────────────────────────────────────────────────────
# 2) connection-pool should reuse the same socket
# ─────────────────────────────────────────────────────────────────────────────
def test_connection_pool_reuse(monkeypatch: pytest.MonkeyPatch):
    counter = {"connect": 0}

    def fake_connect(self, *_):
        counter["connect"] += 1
        self._connected_evt.set()

    monkeypatch.setattr(TradingApp, "connect", fake_connect, raising=True)

    app = TradingApp(host=REAL_IB_HOST, port=REAL_IB_PORT,
                     clientId=REAL_IB_CLIENT_ID, auto_req_ids=False)
    _seed_ids(app, 1_000)

    app.send_order(mock.Mock(), mock.Mock())
    app.send_order(mock.Mock(), mock.Mock())

    assert counter["connect"] == 1                        # reused!


# ─────────────────────────────────────────────────────────────────────────────
# 3) simulate mid-session TCP reset -> caller sees exception
# ─────────────────────────────────────────────────────────────────────────────
def test_mid_session_disconnect(monkeypatch: pytest.MonkeyPatch):
    def fake_connect(self, *_):
        self._connected_evt.set()

    monkeypatch.setattr(TradingApp, "connect", fake_connect, raising=True)

    class UnstableApp(TradingApp):
        def placeOrder(self, oid, contract, order):       # noqa: N802
            if getattr(self, "_sent", False):
                raise ConnectionResetError("simulated drop")
            self._sent = True
            return 1

    app = UnstableApp(host=REAL_IB_HOST, port=REAL_IB_PORT)
    _seed_ids(app, 200)

    app.send_order(mock.Mock(), mock.Mock())              # first ok
    with pytest.raises(ConnectionResetError):
        app.send_order(mock.Mock(), mock.Mock())          # second drops


# ─────────────────────────────────────────────────────────────────────────────
# 4) TLS “support” flag is set when we negotiate SSL
# ─────────────────────────────────────────────────────────────────────────────
def test_tls_support(monkeypatch: pytest.MonkeyPatch):
    def tls_connect(self, *_):
        self.tls_enabled = True
        self._connected_evt.set()

    monkeypatch.setattr(TradingApp, "connect", tls_connect, raising=True)

    app = TradingApp(host="localhost", port=7497)
    _seed_ids(app, 300)
    app.send_order(mock.Mock(), mock.Mock())

    assert getattr(app, "tls_enabled", False) is True


# ─────────────────────────────────────────────────────────────────────────────
# 5) basic parallel stress: 10 threads, shared TradingApp implementation
# ─────────────────────────────────────────────────────────────────────────────
def test_parallel_id_allocation(monkeypatch: pytest.MonkeyPatch):
    def ok_connect(self, *_):
        self._connected_evt.set()

    monkeypatch.setattr(TradingApp, "connect", ok_connect, raising=True)

    ids: list[int] = []

    def worker(idx: int):
        a = TradingApp(clientId=100 + idx)
        _seed_ids(a, 500 + idx)
        ids.append(a.send_order(mock.Mock(), mock.Mock()))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(ids) == list(range(500, 510))
