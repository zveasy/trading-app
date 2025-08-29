#!/usr/bin/env python3
"""
scripts.cr_receiver
───────────────────
Production-grade Cancel/Replace receiver for QuantEngine → IBKR.

Features
- ZMQ PULL to receive CancelReplaceRequest protobuf bytes (proto/cr.proto)
- ZMQ PUB to publish Ack/Reject notifications (JSON) with correlation id
- Persistent proto_id → ib_order_id mapping (SQLite) for idempotency
- Basic validation and risk checks (qty/price bounds, symbol configured)
- Robust IB connection via TradingApp (reconnect, buffering)
- Prometheus metrics for ops visibility

Run
  PYTHONPATH=. python -m scripts.cr_receiver

Env Vars
- ZMQ_ADDR         (default tcp://127.0.0.1:5555)
- ACK_PUB_ADDR     (default tcp://127.0.0.1:6002)
- METRICS_PORT     (default 9100)
- STATE_DB         (default state.sqlite)
- IB_ACCOUNT       (paper/live account)
- ORDER_SYMBOL     (default AAPL)
- MAX_QTY          (optional, int)
- MAX_NOTIONAL     (optional, float)
- JSON_LOGS=1      to enable structured logging (via utils.setup_logger)
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Optional, Set, Tuple
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import zmq
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, start_http_server

from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.order_factory import make_order
from utils.utils import setup_logger

# Prefer the generated protobuf in tests for now
from tests import cr_pb2  # type: ignore

load_dotenv()
logger = setup_logger("CRReceiver")

# ── Metrics ─────────────────────────────────────────────────────────────
msg_rx_total = Counter("cr_msg_received_total", "CR messages received")
msg_err_total = Counter("cr_msg_error_total", "CR messages rejected")
acks_pub_total = Counter("cr_acks_published_total", "Acks published")
proc_latency_ms = Histogram(
    "cr_process_latency_ms", "End-to-end processing latency per message (ms)"
)

# ── Config ──────────────────────────────────────────────────────────────
ZMQ_ADDR = os.getenv("ZMQ_ADDR", "tcp://127.0.0.1:5555")
ACK_PUB_ADDR = os.getenv("ACK_PUB_ADDR", "tcp://127.0.0.1:6002")
STATE_DB = os.getenv("STATE_DB", "state.sqlite")
ACCOUNT_ID = os.getenv("IB_ACCOUNT", "DUH148810")
ORDER_SYMBOL = os.getenv("ORDER_SYMBOL", "AAPL").upper()
MAX_QTY: Optional[int] = int(os.getenv("MAX_QTY", "0")) or None
MAX_NOTIONAL: Optional[float] = float(os.getenv("MAX_NOTIONAL", "0")) or None
MIN_PRICE: Optional[float] = float(os.getenv("MIN_PRICE", "0")) or None
MAX_PRICE: Optional[float] = float(os.getenv("MAX_PRICE", "0")) or None
ALLOWED_SYMBOLS: Optional[Set[str]] = (
    {s.strip().upper() for s in os.getenv("ALLOWED_SYMBOLS", "").split(",") if s.strip()}
    or None
)

# Trading session (e.g. 0930-1600 America/New_York)
TRADING_HOURS = os.getenv("TRADING_HOURS", "0930-1600")
MARKET_TZ = os.getenv("MARKET_TZ", "America/New_York")

# ── Persistence ─────────────────────────────────────────────────────────

def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB, isolation_level=None, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cr_order_map (
          proto_id   INTEGER PRIMARY KEY,
          ib_id      INTEGER NOT NULL,
          last_ts_ns INTEGER,
          status     TEXT
        )
        """
    )
    return conn


def _load_ib_id(conn: sqlite3.Connection, proto_id: int) -> Optional[int]:
    cur = conn.execute("SELECT ib_id FROM cr_order_map WHERE proto_id = ?", (proto_id,))
    row = cur.fetchone()
    return int(row[0]) if row else None


def _save_mapping(conn: sqlite3.Connection, proto_id: int, ib_id: int, ts_ns: int, status: str) -> None:
    conn.execute(
        """
        INSERT INTO cr_order_map (proto_id, ib_id, last_ts_ns, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(proto_id) DO UPDATE SET ib_id=excluded.ib_id, last_ts_ns=excluded.last_ts_ns, status=excluded.status
        """,
        (proto_id, ib_id, ts_ns, status),
    )


# ── Validation ──────────────────────────────────────────────────────────

def _validate(qty: int, price: float) -> Optional[str]:
    if qty <= 0:
        return "qty must be > 0"
    if price <= 0:
        return "price must be > 0"
    if MIN_PRICE is not None and price < MIN_PRICE:
        return f"price {price} below MIN_PRICE {MIN_PRICE}"
    if MAX_PRICE is not None and price > MAX_PRICE:
        return f"price {price} above MAX_PRICE {MAX_PRICE}"
    if MAX_QTY is not None and qty > MAX_QTY:
        return f"qty {qty} exceeds MAX_QTY {MAX_QTY}"
    if MAX_NOTIONAL is not None and (qty * price) > MAX_NOTIONAL:
        return f"notional {qty * price:.2f} exceeds MAX_NOTIONAL {MAX_NOTIONAL:.2f}"
    return None


def _parse_hours(spec: str) -> Tuple[dtime, dtime]:
    start_s, end_s = spec.split("-", 1)
    return (
        dtime(int(start_s[:2]), int(start_s[2:])),
        dtime(int(end_s[:2]), int(end_s[2:])),
    )


def _within_session(now: Optional[datetime] = None) -> bool:
    try:
        start_t, end_t = _parse_hours(TRADING_HOURS)
        tz = ZoneInfo(MARKET_TZ)
        now = now or datetime.now(tz)
        t = now.timetz()
        return (t.replace(tzinfo=None) >= start_t) and (t.replace(tzinfo=None) <= end_t)
    except Exception:
        # if misconfigured, do not block
        return True


# ── ACK helper ─────────────────────────────────────────────────────────

def _publish_ack(sock: zmq.Socket, kind: str, proto_id: int, ib_id: Optional[int], status: str, reason: str = "") -> None:
    msg = {
        "type": kind,  # "CancelReplaceAck" | "CancelReplaceReject"
        "order_id": proto_id,
        "ib_id": ib_id,
        "status": status,
        "reason": reason,
        "ts_ns": time.time_ns(),
    }
    sock.send_multipart([b"order_acks", json.dumps(msg).encode("utf-8")])
    acks_pub_total.inc()


# ── Main loop ───────────────────────────────────────────────────────────

def main() -> None:
    start_http_server(int(os.getenv("METRICS_PORT", "9100")))

    ctx = zmq.Context.instance()

    pull = ctx.socket(zmq.PULL)
    # High-water marks to avoid unbounded memory
    rcv_hwm = int(os.getenv("ZMQ_RCVHWM", "10000"))
    pull.setsockopt(zmq.RCVHWM, rcv_hwm)
    pull.bind(ZMQ_ADDR)
    logger.info("ZMQ PULL bound to %s", ZMQ_ADDR)

    pub = ctx.socket(zmq.PUB)
    snd_hwm = int(os.getenv("ZMQ_SNDHWM", "10000"))
    pub.setsockopt(zmq.SNDHWM, snd_hwm)
    pub.bind(ACK_PUB_ADDR)
    logger.info("ZMQ PUB (acks) bound to %s", ACK_PUB_ADDR)

    conn = _db_connect()
    app = TradingApp(account=ACCOUNT_ID)
    contract = create_contract(ORDER_SYMBOL)

    try:
        while True:
            start = time.perf_counter()
            raw = pull.recv()
            msg_rx_total.inc()

            req = cr_pb2.CancelReplaceRequest()
            try:
                req.ParseFromString(raw)
            except Exception as exc:
                msg_err_total.inc()
                logger.error("Bad protobuf: %s", exc)
                _publish_ack(pub, "CancelReplaceReject", -1, None, "PARSE_ERROR", str(exc))
                continue

            proto_id = int(req.order_id)
            # Prefer nested params but fall back to top-level fields if present
            qty = int(req.params.new_qty) if req.HasField("params") else 0
            price = float(req.params.new_price) if req.HasField("params") else 0.0
            if hasattr(req, "new_price") and req.new_price > 0 and price <= 0:
                price = float(req.new_price)

            # Validate
            err = _validate(qty, price)
            if err:
                msg_err_total.inc()
                logger.warning("Rejecting proto_id=%s: %s", proto_id, err)
                _publish_ack(pub, "CancelReplaceReject", proto_id, None, "REJECT", err)
                continue

            # Session and symbol checks
            if ALLOWED_SYMBOLS is not None and ORDER_SYMBOL not in ALLOWED_SYMBOLS:
                msg_err_total.inc()
                reason = f"symbol {ORDER_SYMBOL} not allowed"
                logger.warning("Rejecting proto_id=%s: %s", proto_id, reason)
                _publish_ack(pub, "CancelReplaceReject", proto_id, None, "REJECT", reason)
                continue
            if not _within_session():
                msg_err_total.inc()
                reason = "outside TRADING_HOURS"
                logger.warning("Rejecting proto_id=%s: %s", proto_id, reason)
                _publish_ack(pub, "CancelReplaceReject", proto_id, None, "REJECT", reason)
                continue

            # Resolve mapping
            ib_id = _load_ib_id(conn, proto_id)
            if ib_id is None:
                # New order
                order = make_order("BUY", "LMT", qty, limit_px=price, account=ACCOUNT_ID)
                try:
                    ib_id = app.send_order(contract, order)
                    _save_mapping(conn, proto_id, ib_id, int(getattr(req, "ts_ns", 0) or time.time_ns()), "SUBMITTED")
                    logger.info("New IB order placed (proto %s → ib %s)", proto_id, ib_id)
                    _publish_ack(pub, "CancelReplaceAck", proto_id, ib_id, "NEW")
                except Exception as exc:
                    msg_err_total.inc()
                    logger.error("Send order failed (proto %s): %s", proto_id, exc)
                    _publish_ack(pub, "CancelReplaceReject", proto_id, None, "ERROR", str(exc))
            else:
                # Replace existing
                status = app.order_statuses.get(ib_id, {}).get("status")
                new_order = make_order("BUY", "LMT", qty, limit_px=price, account=ACCOUNT_ID)
                try:
                    if status in ("Submitted", "PreSubmitted"):
                        app.update_order(contract, new_order, ib_id)
                        logger.info("Cancel/replace sent (proto %s → ib %s)", proto_id, ib_id)
                        _publish_ack(pub, "CancelReplaceAck", proto_id, ib_id, "REPLACE")
                    else:
                        app.placeOrder(ib_id, contract, new_order)
                        logger.info("Modify in place (PendingSubmit) (proto %s → ib %s)", proto_id, ib_id)
                        _publish_ack(pub, "CancelReplaceAck", proto_id, ib_id, "MODIFY")
                    _save_mapping(conn, proto_id, ib_id, int(getattr(req, "ts_ns", 0) or time.time_ns()), "UPDATED")
                except Exception as exc:
                    msg_err_total.inc()
                    logger.error("Replace failed (proto %s ib %s): %s", proto_id, ib_id, exc)
                    _publish_ack(pub, "CancelReplaceReject", proto_id, ib_id, "ERROR", str(exc))

            proc_latency_ms.observe((time.perf_counter() - start) * 1000)

    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        try:
            app.disconnect()
        except Exception:
            pass
        with closing(conn):
            conn.close()
        pub.close(0)
        pull.close(0)
        ctx.term()
        logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    main()
