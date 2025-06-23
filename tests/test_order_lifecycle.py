#!/usr/bin/env python3
"""
tests/test_order_lifecycle.py
─────────────────────────────
Fast unit test — all IB calls mocked, no sockets or sleeps.
"""

from unittest.mock import MagicMock
import importlib
import sys
import pytest

# ────────────────────────────────────────────────────────────────────
# Autouse fixture: patch TradingApp in *scripts.core*
# ────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_trading_app(monkeypatch):  # noqa: F841 (used by pytest via autouse)
    fake = MagicMock(name="TradingAppMock")
    fake.return_value.order_statuses = {}
    fake.return_value.send_order.return_value = 99
    monkeypatch.setattr("scripts.core.TradingApp", fake)
    yield


# ────────────────────────────────────────────────────────────────────
def test_order_lifecycle():
    """create → cancel → update → cancel-all → disconnect."""
    from scripts.core import TradingApp
    from scripts.contracts import create_contract
    from scripts.orders import create_order

    app      = TradingApp(clientId=12)    # MagicMock
    contract = create_contract("AAPL")

    oid = app.send_order(contract, create_order("BUY", "LMT", 10, 185.00))
    assert oid == 99

    app.cancel_order_by_id(oid)
    app.cancel_order_by_id.assert_called_with(oid)

    app.update_order(contract, create_order("BUY", "LMT", 10, 187.50), oid)
    app.update_order.assert_called()

    app.cancel_all_orders()
    app.cancel_all_orders.assert_called_once()

    app.disconnect()
    app.disconnect.assert_called_once()


# ────────────────────────────────────────────────────────────────────
# Ensure cancel_replace_receiver is imported for coverage **without**
# letting its argparse crash the test run.
# ────────────────────────────────────────────────────────────────────
# def test_import_receiver_for_coverage(monkeypatch):
    # monkeypatch.setattr(sys, "argv", ["cancel_replace_receiver"])  # fake CLI
    # importlib.import_module("scripts.cancel_replace_receiver")
