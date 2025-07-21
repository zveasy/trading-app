#!/usr/bin/env python3
"""
scripts.core
────────────
A thin, unified wrapper around Interactive Brokers’ API.

Features
• Handles connection to TWS / IB Gateway (paper or live).
• Guarantees monotonic order-id allocation via _acquire_order_id().
• Caches orderStatus / openOrder callbacks so other code can query them.
• Convenience helpers: send_order(), update_order(), cancel_*().
• Multi-leg helpers: place_bracket_order(), place_oco_order().
• No business logic here – higher-level helpers live in scripts/*.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Any, Optional

import os
import subprocess
import sys
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ib.client import IBClient  # type stubs (EClient alias)
from utils.utils import setup_logger
from scripts.wrapper import IBWrapper  # your subclass of ibapi.wrapper.EWrapper
from risk.throttle import Throttle, ContractSpec

logger = setup_logger()

__all__ = ["TradingApp"]


# ════════════════════════════════════════════════════════════════════════════
class TradingApp(IBWrapper, IBClient):  # IBClient ≡ EClient
    """
    Swiss-army IB connection used by receivers, back-tests, etc.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        clientId: int = 1,
        account: Optional[str] = None,
        *,
        auto_req_ids: bool = False,  # set True if you reconnect per message
        throttle: "Throttle | None" = None,
    ):
        self.account = account
        self.auto_req_ids = auto_req_ids
        self.throttle = throttle or Throttle()

        # Runtime caches populated by callbacks
        self.order_statuses: Dict[int, Dict[str, Any]] = {}
        self.open_orders: Dict[int, Order] = {}

        # Initialise base classes
        IBWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        # Internal state
        self._next_order_id: Optional[int] = None
        self._connected_evt = threading.Event()

        # Start connection + reader thread
        self.connect(host, port, clientId)
        threading.Thread(target=self.run, daemon=True).start()

        # Wait (≤10 s) for nextValidId
        if not self._connected_evt.wait(timeout=10):
            raise RuntimeError("Timed-out waiting for nextValidId from TWS")

        # Optionally force broker to send a *fresh* id block
        if self.auto_req_ids:
            self.reqIds(-1)  # will trigger nextValidId again

        if os.getenv("RELAY_ENABLED") == "1":
            addr = os.getenv("RELAY_ZMQ_ADDR", os.getenv("ZMQ_ADDR", "tcp://*:6002"))
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "scripts.order_status_relay",
                    "--zmq-addr",
                    addr,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    # ────────────────────── EWrapper overrides ────────────────────────────
    def nextValidId(self, orderId: int):
        self._next_order_id = orderId
        self._connected_evt.set()
        logger.info("✅ Connected. Next valid order ID: %s", orderId)

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
        self.order_statuses[orderId] = {
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avgFillPrice": avgFillPrice,
        }

    def openOrder(self, orderId, contract, order, orderState):
        self.open_orders[orderId] = order

    def error(self, reqId, errorCode, errorString):
        """
        Suppress IB’s harmless info codes; log everything else.
        202 – “Order Canceled” (expected during cancel/replace)
        399 – “Parked until market open” (warning)
        2104/2106/2158 – connection / data warnings
        """
        if errorCode in (202, 399, 2104, 2106, 2158):
            return
        logger.error("❌ Error (%s): %s", errorCode, errorString)

    # ────────────────────── internal helpers ───────────────────────────────
    def _acquire_order_id(self) -> int:
        """
        Return a fresh order-id.  If we already hold a valid id, increment it;
        otherwise request one via reqIds(-1).
        """
        if self._next_order_id is not None:
            oid = self._next_order_id
            self._next_order_id += 1
            return oid

        # Fresh request → temporarily capture callback
        evt = threading.Event()

        def _tmp_cb(orderId: int):
            self._next_order_id = orderId
            evt.set()

        orig_cb = self.nextValidId
        self.nextValidId = _tmp_cb  # type: ignore
        self.reqIds(-1)
        evt.wait(5)
        self.nextValidId = orig_cb  # restore  # type: ignore

        if self._next_order_id is None:
            raise RuntimeError("nextValidId never arrived")

        return self._acquire_order_id()  # recurse now that we have one

    # ────────────────────── public helpers ────────────────────────────────
    def send_order(self, contract, order) -> int:
        if self.account and not order.account:
            order.account = self.account

        price = getattr(order, "lmtPrice", 0.0) or getattr(order, "auxPrice", 0.0)
        self.throttle.block_if_needed(
            ContractSpec(symbol=contract.symbol), order.totalQuantity, float(price)
        )

        oid = self._acquire_order_id()
        self.placeOrder(oid, contract, order)
        return oid

    def update_order(self, contract, order, existing_id: int) -> int:
        self.cancelOrder(existing_id)
        return self.send_order(contract, order)

    def place_bracket_order(
        self,
        parent_contract: Contract,
        quantity: int,
        take_profit_px: float,
        stop_loss_px: float,
        tif: str = "DAY",
    ) -> list[int]:
        """Place a three-leg bracket order and return the order ids."""

        from ib_insync import Order as _Order

        base_id = self._acquire_order_id()
        action = "BUY" if quantity > 0 else "SELL"
        qty = abs(quantity)

        parent = _Order(
            action=action,
            orderType="MKT",
            totalQuantity=qty,
            tif=tif,
            transmit=False,
        )
        if self.account and not parent.account:
            parent.account = self.account

        self.throttle.block_if_needed(
            ContractSpec(symbol=parent_contract.symbol), qty, 0.0
        )

        tp = _Order(
            action="SELL" if action == "BUY" else "BUY",
            orderType="LMT",
            totalQuantity=qty,
            lmtPrice=take_profit_px,
            tif=tif,
            parentId=base_id,
            transmit=False,
        )
        if self.account and not tp.account:
            tp.account = self.account

        self.throttle.block_if_needed(
            ContractSpec(symbol=parent_contract.symbol), qty, take_profit_px
        )

        sl = _Order(
            action="SELL" if action == "BUY" else "BUY",
            orderType="STP",
            totalQuantity=qty,
            auxPrice=stop_loss_px,
            tif=tif,
            parentId=base_id,
            transmit=True,
        )
        if self.account and not sl.account:
            sl.account = self.account

        self.throttle.block_if_needed(
            ContractSpec(symbol=parent_contract.symbol), qty, stop_loss_px
        )

        self.placeOrder(base_id, parent_contract, parent)
        self.placeOrder(base_id + 1, parent_contract, tp)
        self.placeOrder(base_id + 2, parent_contract, sl)

        self._next_order_id = base_id + 3
        return [base_id, base_id + 1, base_id + 2]

    def place_oco_order(
        self,
        contract: Contract,
        quantity: int,
        leg1_px: float,
        leg2_px: float,
        tif: str = "DAY",
    ) -> list[int]:
        """Place two linked limit orders (one cancels the other)."""

        from ib_insync import Order as _Order

        base_id = self._acquire_order_id()
        action = "BUY" if quantity > 0 else "SELL"
        qty = abs(quantity)
        oca_group = f"OCO-{base_id}"

        first = _Order(
            action=action,
            orderType="LMT",
            totalQuantity=qty,
            lmtPrice=leg1_px,
            tif=tif,
            ocaGroup=oca_group,
            ocaType=1,
            transmit=False,
        )
        if self.account and not first.account:
            first.account = self.account

        self.throttle.block_if_needed(
            ContractSpec(symbol=contract.symbol), qty, leg1_px
        )

        second = _Order(
            action=action,
            orderType="LMT",
            totalQuantity=qty,
            lmtPrice=leg2_px,
            tif=tif,
            ocaGroup=oca_group,
            ocaType=1,
            transmit=True,
        )
        if self.account and not second.account:
            second.account = self.account

        self.throttle.block_if_needed(
            ContractSpec(symbol=contract.symbol), qty, leg2_px
        )

        self.placeOrder(base_id, contract, first)
        self.placeOrder(base_id + 1, contract, second)

        self._next_order_id = base_id + 2
        return [base_id, base_id + 1]

    # Bulk helpers
    def cancel_order_by_id(self, order_id: int):
        self.cancelOrder(order_id)

    def cancel_all_orders(self):
        self.reqGlobalCancel()

    # Convenience snapshots
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

    def close_all_positions(self) -> None:
        """Liquidate all open positions using market orders."""
        from ib_insync import Stock, Order as _Order

        positions = self.request_positions()
        pos_iter = positions.values() if isinstance(positions, dict) else positions
        for pos in pos_iter:
            qty = pos.get("position") if isinstance(pos, dict) else getattr(pos, "position", 0)
            sym = pos.get("symbol") if isinstance(pos, dict) else getattr(pos, "symbol", "")
            if not qty or not sym:
                continue

            action = "SELL" if qty > 0 else "BUY"
            contract = Stock(sym, "SMART", "USD")
            order = _Order(
                action=action,
                orderType="MKT",
                totalQuantity=abs(int(qty)),
                tif="DAY",
            )
            if self.account and not getattr(order, "account", None):
                order.account = self.account
            self.placeOrder(self._acquire_order_id(), contract, order)

        self.cancel_all_orders()


# ════════════════════════════════════════════════════════════════════════════
# Demo mode (run: python -m scripts.core)
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from scripts.contracts import create_contract
    from scripts.orders import create_order

    app = TradingApp()  # defaults to paper 7497
    contract = create_contract("AAPL")
    order = create_order("BUY", "MKT", 1)

    logger.info("Placing 1-share test order …")
    app.send_order(contract, order)

    time.sleep(3)
    app.disconnect()
