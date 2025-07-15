#!/usr/bin/env python3
"""
cancel_replace_receiver.py  –  v3  (persistent + metrics + retry)

• Persistent state (SQLite)   (proto_id, sym) → ib_id
• Prometheus metrics exposed on :9100/metrics
• Retry back-off helper
• Graceful shutdown

CLI
───
python -m scripts.cancel_replace_receiver \
        --account DUH148810 \
        --host    127.0.0.1 \
        --port    7497 \
        --zmq     "tcp://*:5555" \
        --db      var/state.db
"""

from __future__ import annotations

# ── stdlib ────────────────────────────────────────────────────────────────
import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

# ── 3rd-party ─────────────────────────────────────────────────────────────
import zmq
from dotenv import load_dotenv

# ── project imports ───────────────────────────────────────────────────────
from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.order_factory import make_order
from scripts.helpers import wait_order_active                # noqa: F401 (used elsewhere)
from scripts.state_store import StateStore                   # tiny SQLite wrapper
from scripts.retry import RetryRegistry, SHOULD_RETRY

# Prometheus metrics
from scripts.metrics_server import (
    start as start_metrics,
    RECEIVER_MSGS, RECEIVER_ERRORS, IB_RETRIES, INFLIGHT_CONN,
    RECEIVER_BACKOFFS, RETRY_RESETS, IB_ERROR_CODES,
    orders_by_symbol, orders_by_type, order_latency, orders_filled,
    orders_canceled, orders_rejected, queue_depth
)


# ═════════════════════════════════  Boot  ════════════════════════════════
load_dotenv()                            # allow .env overrides
start_metrics(int(os.getenv("METRICS_PORT", "9100")))  # exporter on http://localhost:9100/metrics

# ── CLI args ──────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("IB Cancel/Replace Receiver (persistent+metrics)")
    p.add_argument("--account", default=os.getenv("IB_ACCOUNT"),
                   help="IB account (paper/live)")
    p.add_argument("--host",    default=os.getenv("IB_HOST", "127.0.0.1"),
                   help="TWS / IBGW host")
    p.add_argument("--port",    type=int,
                   default=int(os.getenv("IB_PORT", "7497")),
                   help="TWS / IBGW port")
    p.add_argument("--zmq",     default=os.getenv("ZMQ_ADDR", "tcp://*:5555"),
                   help="ZMQ PULL bind addr")
    p.add_argument("--db",      default=os.getenv("STATE_DB", "var/state.db"),
                   help="SQLite DB file")
    return p.parse_args()


ARGS       = parse_args()
ACCOUNT_ID = ARGS.account or os.getenv("IB_ACCOUNT", "DUH148810")

# ── Persistent map --------------------------------------------------------
store = StateStore(ARGS.db)
PROTO_TO_IB: Dict[Tuple[int, str], int] = store.load()
print(f"🔄  Loaded {len(PROTO_TO_IB)} rows from {ARGS.db}")

# ── ZMQ -------------------------------------------------------------------
ctx  = zmq.Context.instance()
sock = ctx.socket(zmq.PULL)
sock.bind(ARGS.zmq)
print(f"Receiver listening on {ARGS.zmq} …")

# ── Retry helper ----------------------------------------------------------
retry_reg = RetryRegistry(max_attempts=3, base_delay=1.0)

# ── Graceful shutdown -----------------------------------------------------
SHUTDOWN = False


def _sig_handler(_sig, _frm):
    global SHUTDOWN
    SHUTDOWN = True
    print("\n🔌  Shutdown requested … finishing loop")


signal.signal(signal.SIGINT, _sig_handler)
signal.signal(signal.SIGTERM, _sig_handler)

# ── Type-safe order builder ----------------------------------------------
def make_limit_order(side: str, qty: int, px: float, acct: str):
    return make_order(action=side, order_type="LMT",
                      quantity=qty, limit_px=px, account=acct)


# ── protobuf schema -------------------------------------------------------
# (import kept here to avoid heavy cost if script used elsewhere)
from tests import cr_pb2  # noqa: E402

# ═════════════════════════════  Main loop  ═══════════════════════════════
while not SHUTDOWN:
    # 1) non-blocking poll
    try:
        raw = sock.recv(flags=zmq.NOBLOCK)
    except zmq.Again:
        # If using a queue, update metric
        # queue_depth.set(queue.qsize()) # Uncomment if you have a queue object
        time.sleep(0.05)
        continue

    RECEIVER_MSGS.inc()

    # 2) decode protobuf
    req = cr_pb2.CancelReplaceRequest()
    try:
        req.ParseFromString(raw)
    except Exception as exc:                       
        RECEIVER_ERRORS.inc()
        print("❌  Protobuf parse error:", exc)
        continue

    # 3) extract fields
    proto_id = req.order_id
    qty, price = req.params.new_qty, req.params.new_price
    sym = getattr(req, "symbol", "") or "AAPL"
    key = (proto_id, sym)
    print(f"📨  RX proto={proto_id} sym={sym} qty={qty} px={price}")

    # Increment per-symbol metric
    orders_by_symbol.labels(symbol=sym).inc()
    orders_by_type.labels(type="NEW" if key not in PROTO_TO_IB else "REPLACE").inc()

    # 4) retry gate
    if not retry_reg.ready(key):
        RECEIVER_BACKOFFS.inc()
        continue

    app = None
    try:
        # 5) IB connect
        INFLIGHT_CONN.inc()
        app = TradingApp(host=ARGS.host, port=ARGS.port, account=ACCOUNT_ID)
        contract = create_contract(sym)

        # Wrap main order processing in latency histogram
        with order_latency.labels(symbol=sym).time():
            # 6) NEW vs REPLACE
            if key not in PROTO_TO_IB:
                ib_id = app.send_order(contract, make_limit_order("BUY", qty, price, ACCOUNT_ID))
                PROTO_TO_IB[key] = ib_id
                store.upsert(*key, ib_id)
                print(f"✅  NEW order (proto {proto_id}/{sym} ➜ ib {ib_id})")
                # Simulate events (in your app, call on real status events):
                orders_filled.inc()
            else:
                ib_id = PROTO_TO_IB[key]
                status = (app.order_statuses.get(ib_id) or {}).get("status")
                new_order = make_limit_order("BUY", qty, price, ACCOUNT_ID)

                if status in ("Submitted", "PreSubmitted"):
                    app.update_order(contract, new_order, ib_id)
                    print(f"🔄  Cancel/replace ({proto_id}/{sym} ➜ ib {ib_id})")
                    orders_filled.inc()
                else:
                    app.placeOrder(ib_id, contract, new_order)
                    print(f"✏️  Modify in place ({proto_id}/{sym} ➜ ib {ib_id})")
                    orders_canceled.inc()

                store.upsert(*key, ib_id)
                retry_reg.on_success(key)
                RETRY_RESETS.inc()

    except Exception as ib_err:
        RECEIVER_ERRORS.inc()
        orders_rejected.inc()
        code = getattr(ib_err, "code", None)
        if code is not None:
            IB_ERROR_CODES.labels(code=str(code)).inc()
        if code in SHOULD_RETRY:
            IB_RETRIES.inc()
            retry_reg.on_error(key, code)
        print("❌  IB error:", ib_err)

    finally:
        if app:
            app.disconnect()
            INFLIGHT_CONN.dec()
        time.sleep(1.0)  # allow callbacks / avoid hammering TWS
