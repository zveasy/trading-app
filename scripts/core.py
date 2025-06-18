#!/usr/bin/env python3
"""
scripts.core
────────────
A thin, unified wrapper around Interactive Brokers' API that:

• Connects to TWS / IB Gateway (paper or live)
• Guarantees monotonic order-id allocation via _acquire_order_id()
• Caches orderStatus / openOrder events for inspection
• Exposes helpers: send_order(), update_order(), cancel_order_by_id(), cancel_all_orders()
• Provides convenience methods for portfolio / position snapshots

Only IB-specific plumbing lives here.  Higher-level helpers
(e.g. contracts.py, orders.py) stay in scripts/* to avoid circular imports.
"""

from __future__ import annotations  # ← must be the first import on Py < 3.11

import threading
import time
from typing import Dict, Any

from ibapi.client import EClient
from ibapi.order import Order
from ib.client import IBClient        # type-stubs (same class as EClient)
from utils.utils import setup_logger
from scripts.wrapper import IBWrapper  # your subclass of ibapi.wrapper.EWrapper

logger = setup_logger()


# ════════════════════════════════════════════════════════════════════════════
class TradingApp(IBWrapper, IBClient):  # IBClient == EClient
    """
    Single “Swiss-army” connection object.
    Instantiated once per logical task (e.g. cancel/replace receiver).
    """

    # ───────────────────────── ctor ────────────────────────────────────────
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        clientId: int = 1,
        account: str | None = None,
    ):
        # User-supplied account (e.g. DUH148810)
        self.account = account

        # Runtime caches populated by callbacks
        self.order_statuses: Dict[int, Dict[str, Any]] = {}
        self.open_orders: Dict[int, Order] = {}

        # Initialize IB API base classes
        IBWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        # Internal orchestration
        self._next_order_id: int | None = None
        self._connected_evt = threading.Event()

        # Start connection + reader thread
        self.connect(host, port, clientId)
        threading.Thread(target=self.run, daemon=True).start()
        # Wait until nextValidId arrives (max 10 s)
        self._connected_evt.wait(timeout=10)

    # ─────────────────────── EWrapper overrides ────────────────────────────
    def nextValidId(self, orderId: int):
        """IB will call this on successful connection."""
        self._next_order_id = orderId
        self._connected_evt.set()
        logger.info(f"✅ Connected. Next valid order ID: {orderId}")

    def orderStatus(
        self,
        orderId,
        status,
        filled,
        remaining,
        avgFillPrice,
        permId,
        parentId,
        lastFillPrice,
        clientId,
        whyHeld,
        mktCapPrice,
    ):
        """Store latest status in dict for quick lookup."""
        self.order_statuses[orderId] = {
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
        }

    def openOrder(self, orderId, contract, order, orderState):
        """Cache the Order object so callers can inspect / clone."""
        self.open_orders[orderId] = order

    def error(self, reqId, errorCode, errorString):
        """
        Filter out IB's “informational” codes, including 202 (Order Canceled).
        """
        if errorCode in (202, 2104, 2106, 2158):
            return
        logger.error(f"❌ Error ({errorCode}): {errorString}")

    # ────────────────────────────── helper ────────────────────────────────────
    def wait_order_active(app: TradingApp, ib_id: int, timeout: float = 3.0) -> bool:
        """
        Poll an order until it reaches Submitted / PreSubmitted state.

        Parameters
        ----------
        app      : TradingApp
            The live TradingApp instance.
        ib_id    : int
            IB-assigned orderId we’re waiting on.
        timeout  : float
            Seconds to wait before giving up.

        Returns
        -------
        bool  –  True if the order became active, False on timeout.
        """
        start = time.time()
        while time.time() - start < timeout:
            info = app.order_statuses.get(ib_id)      # dict or None
            if info and info.get("status") in ("Submitted", "PreSubmitted"):
                return True
            time.sleep(0.25)
        return False
    # ────────────────────────────── EWrapper overrides ────────────────────────

    def error(self, reqId, errorCode, errorString):
        """Filter out noisy ‘informational’ codes."""
        if errorCode not in (2104, 2106, 2158):
            logger.error(f"❌ Error ({errorCode}): {errorString}")

    # ───────────────────── internal helpers ────────────────────────────────
    def _acquire_order_id(self) -> int:
        """
        Always returns a fresh order-id.

        • If we already hold a valid _next_order_id, increment & return.
        • Otherwise, request it with reqIds(-1) and block (≤5 s).
        """
        if self._next_order_id is not None:
            oid = self._next_order_id
            self._next_order_id += 1
            return oid

        wait_evt = threading.Event()

        def _tmp_cb(orderId: int):
            self._next_order_id = orderId
            wait_evt.set()

        # Temporarily hijack nextValidId
        orig_cb = self.nextValidId
        self.nextValidId = _tmp_cb  # type: ignore
        self.reqIds(-1)
        wait_evt.wait(timeout=5)
        self.nextValidId = orig_cb  # restore  # type: ignore

        if self._next_order_id is None:
            raise RuntimeError("nextValidId never arrived from TWS")

        return self._acquire_order_id()  # recurse now that we have one

    # ───────────────────────── public API ──────────────────────────────────
    def send_order(self, contract, order) -> int:
        """
        Places a *new* order and returns IB-assigned orderId.
        Always sets order.account if missing and self.account is provided.
        """
        if self.account and not order.account:
            order.account = self.account
        oid = self._acquire_order_id()
        self.placeOrder(oid, contract, order)
        return oid

    def update_order(self, contract, order, existing_id: int) -> int:
        """
        Cancel an existing order and immediately place a replacement.
        Returns the *new* IB orderId.
        """
        self.cancelOrder(existing_id)
        return self.send_order(contract, order)

    def cancel_order_by_id(self, order_id: int):
        self.cancelOrder(order_id)

    def cancel_all_orders(self):
        self.reqGlobalCancel()

    # ───────── optional convenience wrappers (portfolio / positions) ──────
    def request_positions(self):
        self.positions: Dict[str, Any] = {}
        self.reqAccountUpdates(True, self.account or "")
        time.sleep(2)
        return self.positions

    def request_portfolio(self):
        self.portfolio: Dict[str, Any] = {}
        self.reqAccountUpdates(True, self.account or "")
        time.sleep(2)
        return self.portfolio

    def wait_order_active(app: TradingApp, ib_id: int, timeout: float = 3.0) -> bool:
        """Return True once order moves into Submitted/PreSubmitted, else False."""
        start = time.time()
        while time.time() - start < timeout:
            info = app.order_statuses.get(ib_id)        # <- dict or None
            if info and info.get("status") in ("Submitted", "PreSubmitted"):
                return True
            time.sleep(0.25)
        return False


# ════════════════════════════════════════════════════════════════════════════
# rudimentary CLI test (called if run as script)                              #
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from scripts.contracts import create_contract
    from scripts.orders import create_order

    app = TradingApp()  # default host/port (7497 paper)
    contract = create_contract("AAPL")
    order    = create_order("BUY", "MKT", 1)

    logger.info("Placing 1-share test order …")
    app.send_order(contract, order)

    # Wait a couple seconds so callbacks print
    time.sleep(3)
    app.disconnect()
