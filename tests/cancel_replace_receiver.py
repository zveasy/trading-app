#!/usr/bin/env python3
"""
tests.cancel_replace_receiver
─────────────────────────────
• Listens on tcp://*:5555 for CancelReplaceRequest protobufs
• Maps proto_id ➜ IB order id
• Performs smart cancel/replace
Run from project root:
    PYTHONPATH=. python -m tests.cancel_replace_receiver
"""

from __future__ import annotations

import os, time, zmq
from dotenv import load_dotenv
from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.order_factory import make_order
from scripts.helpers import wait_order_active
from tests import cr_pb2  # generated protobuf

load_dotenv()
ACCOUNT_ID = os.getenv("IB_ACCOUNT", "DUH148810")  # default paper ID
SYMBOL      = os.getenv("ORDER_SYMBOL", "AAPL")

ctx  = zmq.Context()
sock = ctx.socket(zmq.PULL)
sock.bind("tcp://*:5555")
print("Receiver listening on tcp://*:5555 …")

PROTO_TO_IB: dict[int, int] = {}


def make_limit_order(action: str, qty: int, price: float, account: str):
    return make_order(
        action=action, order_type="LMT",
        quantity=qty, limit_px=price, account=account
    )


while True:
    raw = sock.recv()
    req = cr_pb2.CancelReplaceRequest()
    try:
        req.ParseFromString(raw)
    except Exception as exc:
        print(f"❌  Bad protobuf: {exc}")
        continue

    proto_id, qty, price = req.order_id, req.params.new_qty, req.params.new_price
    print(f"📨  RX proto={proto_id} qty={qty} px={price}")

    app      = TradingApp(account=ACCOUNT_ID)
    contract = create_contract(SYMBOL)

    if proto_id not in PROTO_TO_IB:
        # ── NEW IB order ────────────────────────────────────────────────
        ib_id = app.send_order(contract, make_limit_order("BUY", qty, price, ACCOUNT_ID))
        PROTO_TO_IB[proto_id] = ib_id
        print(f"✅  New IB order placed (proto {proto_id} ➜ ib {ib_id})")

    else:
        # ── SMART cancel/replace ───────────────────────────────────────
        ib_id  = PROTO_TO_IB[proto_id]
        status = app.order_statuses.get(ib_id, {}).get("status")

        new_ord = make_limit_order("BUY", qty, price, ACCOUNT_ID)

        if status in ("Submitted", "PreSubmitted"):
            app.update_order(contract, new_ord, ib_id)
            print(f"🔄 Cancel/replace sent (proto {proto_id} ➜ ib {ib_id})")
        else:
            # PendingSubmit → in-place modify
            app.placeOrder(ib_id, contract, new_ord)
            print(f"✏️  Modify in place (PendingSubmit) (proto {proto_id} ➜ ib {ib_id})")

    time.sleep(1)   # flush callbacks
    app.disconnect()
