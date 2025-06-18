#!/usr/bin/env python3
"""
cancel_replace_receiver.py
─────────────────────────────────────────────────────────────────────────
• Listens on tcp://*:5555 for CancelReplaceRequest protobuf messages
• On first sight of a proto_id  → places a NEW IB order
• On subsequent messages        → performs a smart cancel/replace
• Keeps an in-memory map proto_id ➜ ib_order_id
"""

from __future__ import annotations

import os
import time
import zmq
from dotenv import load_dotenv

from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.order_factory import make_order
from tests import cr_pb2


# ── ENV / configuration ────────────────────────────────────────────────────
load_dotenv()
ACCOUNT_ID = os.getenv("IB_ACCOUNT", "DUH148810")
SYMBOL     = os.getenv("ORDER_SYMBOL", "AAPL")

# ── ZMQ set-up ─────────────────────────────────────────────────────────────
ctx  = zmq.Context()
sock = ctx.socket(zmq.PULL)
sock.bind("tcp://*:5555")
print("Python ZMQ receiver listening on tcp://*:5555 …")

# ── proto_id ➜ ib_order_id map ─────────────────────────────────────────────
PROTO_TO_IB: dict[int, int] = {}


# ── Helpers ────────────────────────────────────────────────────────────────
def make_limit_order(action: str, qty: int, price: float, account: str):
    return make_order(
        action=action,
        order_type="LMT",
        quantity=qty,
        limit_px=price,
        account=account,
    )


def wait_order_active(app: TradingApp, ib_id: int, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = app.order_statuses.get(ib_id)
        if info and info.get("status") in ("Submitted", "PreSubmitted"):
            return True
        time.sleep(0.1)
    return False


# ── Main event loop ────────────────────────────────────────────────────────
while True:
    raw = sock.recv()                   # blocking
    req = cr_pb2.CancelReplaceRequest()
    try:
        req.ParseFromString(raw)
    except Exception as exc:
        print(f"❌  Could not parse protobuf: {exc}")
        continue

    proto_id = req.order_id
    qty      = req.params.new_qty
    price    = req.params.new_price
    print(f"📨  RX proto={proto_id} | qty={qty} | px={price}")

    # Connect to IB
    app      = TradingApp(account=ACCOUNT_ID)
    contract = create_contract(SYMBOL)

    if proto_id not in PROTO_TO_IB:
        # First time: place NEW order
        ib_id = app.send_order(
            contract,
            make_limit_order("BUY", qty, price, ACCOUNT_ID),
        )
        PROTO_TO_IB[proto_id] = ib_id
        print(f"✅  New IB order placed (proto {proto_id} ➜ ib {ib_id})")

    else:
        # Subsequent message → smart cancel/replace
        ib_id = PROTO_TO_IB[proto_id]
        info  = app.order_statuses.get(ib_id)
        state = info.get("status") if info else None

        new_ib_order = make_limit_order("BUY", qty, price, ACCOUNT_ID)

        if state in ("Submitted", "PreSubmitted"):
            # Active → classic cancel + replace
            app.update_order(contract, new_ib_order, ib_id)
            print(f"🔄 Cancel/replace sent (proto {proto_id} ➜ ib {ib_id})")
        else:
            # Still PendingSubmit (or unknown) → in-place modify
            app.placeOrder(ib_id, contract, new_ib_order)
            print(
                f"✏️  In-place modify sent (PendingSubmit) "
                f"(proto {proto_id} ➜ ib {ib_id})"
            )

    time.sleep(1.0)  # allow callbacks
    app.disconnect()
