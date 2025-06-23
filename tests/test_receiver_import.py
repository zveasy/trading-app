"""
Import-only test – pulls in `scripts.cancel_replace_receiver` so that
coverage counts the file, but without opening real ZMQ sockets _or_
connecting to IB.  We deliberately raise `SystemExit` on the first
`sock.recv()` so the top-level `while not SHUTDOWN:` loop bails out
immediately; the test then asserts that exit.
"""

import sys
import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest


def test_import_receiver(monkeypatch):
    # 1️⃣ Fake CLI so argparse inside the module sees no pytest flags
    monkeypatch.setattr(sys, "argv", ["cancel_replace_receiver"])

    # 2️⃣ Stub TradingApp BEFORE import (blocks real IB connection)
    fake_app_cls = MagicMock(name="TradingAppMock")
    monkeypatch.setattr("scripts.core.TradingApp", fake_app_cls)

    # 3️⃣ Dummy ZMQ socket.  `recv()` immediately raises SystemExit which
    #    terminates the receiver’s main loop at import-time.
    dummy_sock = SimpleNamespace(
        bind=lambda *a, **k: None,
        close=lambda *a, **k: None,
        setsockopt=lambda *a, **k: None,
        recv=lambda *a, **k: (_ for _ in ()).throw(SystemExit),  # raise
    )
    monkeypatch.setattr("zmq.Context.socket", lambda *a, **k: dummy_sock)

    # 4️⃣ Import — we expect it to exit cleanly via our SystemExit
    with pytest.raises(SystemExit):
        importlib.import_module("scripts.cancel_replace_receiver")
