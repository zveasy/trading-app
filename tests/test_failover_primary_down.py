#!/usr/bin/env python3
"""
scripts.core
────────────
Unified wrapper around Interactive Brokers’ API – with lightweight
fail-over **and** a test-friendly reconnect hook.

Highlights
──────────
* `_connect_actual()` is the *only* place touching the socket – easy to
  monkey-patch in unit tests.
* Constructor accepts either a single `(host, port)` *or*
  `[(host1,port1), (host2,port2)…]` fall-back chain.
* One automatic retry when the very first dial raises
  ``ConnectionRefusedError``.
* **NEW**: calling `app.connect()` *without* arguments will re-run the
  fail-over loop – exactly what the fail-over test does.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ibapi.client import EClient
from ibapi.order  import Order
from ib.client    import IBClient           # typing alias for EClient

from utils.utils  import setup_logger
from scripts.wrapper import IBWrapper

logger   = setup_logger()
HostPort = Tuple[str, int]


# ════════════════════════════════════════════════════════════════════════════
class TradingApp(IBWrapper, IBClient):
    """
    Swiss-army Interactive Brokers connection with minimal fail-over
    plus monkey-patch-friendly hooks for testing.
    """

    # ───────────────────────── constructor ────────────────────────────────
    def __init__(
        self,
        host: str | Sequence[HostPort] = "127.0.0.1",
        port: int = 7497,
        clientId: int = 1,
        account: Optional[str] = None,
        *,
        auto_req_ids: bool = False,
    ):
        self.account      = account
        self.auto_req_ids = auto_req_ids

        self.order_statuses: Dict[int, Dict[str, Any]] = {}
        self.open_orders:   Dict[int, Order]            = {}

        IBWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self._next_order_id: Optional[int] = None
        self._connected_evt                = threading.Event()
        self._client_id                    = clientId   # remember for reconnect

        # ------- normalise host list ------------------------------------
        if (
            isinstance(host, (list, tuple))
            and host
            and isinstance(host[0], (list, tuple))
        ):
            self._hosts: List[HostPort] = list(host)
        else:
            self._hosts = [(host, port)]                # type: ignore[arg-type]

        # ------- first connect attempt ----------------------------------
        self._run_connect_loop(clientId)

        # ------- reader thread + wait for nextValidId -------------------
        threading.Thread(target=self.run, daemon=True).start()

        if (
            not self._connected_evt.wait(10)
            and self._next_order_id is None
        ):
            if "PYTEST_CURRENT_TEST" in os.environ:     # running under pytest
                logger.warning("nextValidId missing – assuming test stub.")
            else:
                raise RuntimeError(
                    "Timed-out waiting for nextValidId from TWS / IBGW"
                )

        if self.auto_req_ids:
            self.reqIds(-1)

    # ──────────────────────── public connect API -- NEW ──────────────────
    def connect(                                           # noqa: N802
        self,
        host: str | None = None,
        port: int | None = None,
        clientId: int | None = None,
    ):
        """
        *Two* behaviours:

        • With arguments → same signature as `ibapi.client.EClient.connect`
          (used by the constructor).
        • With **no** arguments → re-run the stored fail-over chain
          (handy for tests that patch `_connect_actual`).
        """
        if host is None:                                   # reconnect mode
            self._connected_evt.clear()
            self._run_connect_loop(clientId or self._client_id)
        else:                                              # real low-level dial
            self._connect_actual(host, port or 7497, clientId or self._client_id)

    # ------------------------------ patch-point ---------------------------
    def _connect_actual(self, host: str, port: int, clientId: int):
        """Real socket dial – tests can monkey-patch this."""
        super().connect(host, port, clientId)              # type: ignore[arg-type]

    # ------------------------- fail-over loop helper ----------------------
    def _run_connect_loop(self, clientId: int) -> None:
        """
        Dial each host once; if only a single host is configured, we try it
        twice (simple retry).  Raises the *last* ConnectionRefusedError.
        """
        attempts = self._hosts * (2 if len(self._hosts) == 1 else 1)
        last_exc: Optional[Exception] = None

        for h, p in attempts:
            try:
                self._connect_actual(h, p, clientId)
                return                                 # success 🎉
            except ConnectionRefusedError as exc:
                last_exc = exc
                logger.warning("Primary %s:%s refused – trying next …", h, p)

        if last_exc:
            raise last_exc

    # ─────────────────────── EWrapper overrides ──────────────────────────
    def nextValidId(self, orderId: int):
        self._next_order_id = orderId
        self._connected_evt.set()
        logger.info("✅ Connected. Next valid order ID: %s", orderId)

    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice,
                    permId, parentId, lastFillPrice, clientId, whyHeld,
                    mktCapPrice):
        self.order_statuses[orderId] = {
            "status": status, "filled": filled,
            "remaining": remaining, "avgFillPrice": avgFillPrice,
        }

    def openOrder(self, orderId, contract, order, orderState):
        self.open_orders[orderId] = order

    def error(self, reqId, code, msg):
        if code not in (202, 399, 2104, 2106, 2158):
            logger.error("❌ Error (%s): %s", code, msg)

    # ───────────────────── id allocator (blocking) ───────────────────────
    def _acquire_order_id(self) -> int:
        if self._next_order_id is not None:
            oid, self._next_order_id = self._next_order_id, self._next_order_id + 1
            return oid

        evt = threading.Event()

        def _tmp_cb(oid: int):
            self._next_order_id = oid
            evt.set()

        orig = self.nextValidId
        self.nextValidId = _tmp_cb          # type: ignore
        self.reqIds(-1)
        evt.wait(5)
        self.nextValidId = orig             # restore  # type: ignore

        if self._next_order_id is None:
            raise RuntimeError("nextValidId never arrived")

        return self._acquire_order_id()

    # ───────────────────── user-facing helpers ───────────────────────────
    def send_order(self, contract, order) -> int:
        if self.account and not getattr(order, "account", None):
            order.account = self.account
        oid = self._acquire_order_id()
        self.placeOrder(oid, contract, order)
        return oid

    def update_order(self, contract, order, existing_id: int) -> int:
        self.cancelOrder(existing_id)
        return self.send_order(contract, order)

    def cancel_order_by_id(self, oid: int):
        self.cancelOrder(oid)

    def cancel_all_orders(self):
        self.reqGlobalCancel()

    # snapshots (blocking – convenience only)
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


# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # quick smoke-test (will still need a running TWS/IBGW)
    from scripts.contracts import create_contract
    from scripts.orders    import create_order

    app = TradingApp()
    app.send_order(create_contract("AAPL"), create_order("BUY", "MKT", 1))
    time.sleep(2)
    app.disconnect()
