from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Optional, Set, Tuple, Dict, Any
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import zmq
from dotenv import load_dotenv
from prometheus_client import Counter, Histogram, start_http_server

from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.order_factory import make_order
from utils.utils import setup_logger
from scripts.validation import EnvelopeModel, SimpleOrderModel

# Optional: protobuf Envelope support if generated code is available
try:  # pragma: no cover
    from shared_proto import envelope_pb2 as envpb  # type: ignore
except Exception:  # pragma: no cover
    envpb = None  # type: ignore

# Optional: protobuf Ack support
try:  # pragma: no cover
    from shared_proto import ack_pb2 as ackpb  # type: ignore
except Exception:  # pragma: no cover
    ackpb = None  # type: ignore

# For now we reuse the test-generated CancelReplaceRequest proto
# until shared codegen is added for runtime.
from tests import cr_pb2  # type: ignore

load_dotenv()
logger = setup_logger(name="V1Receiver", log_file="v1_receiver.log")
V1_DRY_RUN = os.getenv("V1_DRY_RUN", "0") == "1"

# Simple dry-run TradingApp that doesn't require TWS/IBG
class _DryRunApp:
    def __init__(self, *a, **k):
        self._next_id = 10000

    def send_order(self, contract, order):  # type: ignore
        oid = self._next_id
        self._next_id += 1
        return oid

    def replace_order(self, ib_id: int, order):  # type: ignore
        # no-op for dry run
        return True

# Addresses and config
ZMQ_ADDR = os.getenv("V1_ZMQ_ADDR", os.getenv("ZMQ_ADDR", "tcp://127.0.0.1:5556"))
ACK_PUB_ADDR = os.getenv("V1_ACK_PUB_ADDR", os.getenv("ACK_PUB_ADDR", "tcp://127.0.0.1:6003"))
STATE_DB = os.getenv("STATE_DB", "state.sqlite")
ACCOUNT_ID_DEFAULT = os.getenv("IB_ACCOUNT", "DUH148810")
MAX_QTY: Optional[int] = int(os.getenv("MAX_QTY", "0")) or None
MAX_NOTIONAL: Optional[float] = float(os.getenv("MAX_NOTIONAL", "0")) or None
MIN_PRICE: Optional[float] = float(os.getenv("MIN_PRICE", "0")) or None
MAX_PRICE: Optional[float] = float(os.getenv("MAX_PRICE", "0")) or None
ALLOWED_SYMBOLS: Optional[Set[str]] = (
    {s.strip().upper() for s in os.getenv("ALLOWED_SYMBOLS", "").split(",") if s.strip()} or None
)

TRADING_HOURS = os.getenv("TRADING_HOURS", "0930-1600")
MARKET_TZ = os.getenv("MARKET_TZ", "America/New_York")

# Metrics
METRICS_PORT = int(os.getenv("V1_METRICS_PORT", "9102"))
recv_total = Counter("v1_receiver_received_total", "Total inbound envelope messages")
reject_total = Counter("v1_receiver_rejected_total", "Total rejected envelope messages")
route_total = Counter("v1_receiver_routed_total", "Messages routed by type", ["msg_type"])  # type: ignore
ack_total = Counter("v1_receiver_ack_total", "Total acks published", ["status"])  # type: ignore
process_latency = Histogram("v1_receiver_processing_seconds", "Message processing latency seconds")
ack_latency = Histogram("v1_receiver_ack_latency_seconds", "ACK publish latency seconds")
ack_reason_total = Counter("v1_receiver_ack_reason_total", "ACKs by reason", ["reason"])  # type: ignore

# Mode: JSON envelopes (default) or protobuf envelope if env set and code exists
PROTO_MODE = os.getenv("V1_PROTO_MODE", "0") == "1" and envpb is not None
PROTO_ACK_MODE = os.getenv("V1_PROTO_ACK_MODE", "0") == "1" and ackpb is not None

# Track last receive timestamp for latency metrics
LAST_RECV_TS: Optional[float] = None


# Persistence helpers (reuse proto_id mapping for CancelReplace)
SQL_INIT = """
CREATE TABLE IF NOT EXISTS cr_mapping (
    proto_id INTEGER PRIMARY KEY,
    ib_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS simple_order_mapping (
    idempotency_key TEXT PRIMARY KEY,
    order_id INTEGER NOT NULL
);
"""

SQL_GET = "SELECT ib_id FROM cr_mapping WHERE proto_id = ?"
SQL_PUT = "INSERT OR REPLACE INTO cr_mapping (proto_id, ib_id) VALUES (?, ?)"
SQL_SO_GET = "SELECT order_id FROM simple_order_mapping WHERE idempotency_key = ?"
SQL_SO_PUT = "INSERT OR REPLACE INTO simple_order_mapping (idempotency_key, order_id) VALUES (?, ?)"


def _db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STATE_DB, timeout=5.0, isolation_level=None)
    with closing(conn.cursor()) as cur:
        # Use executescript to run multiple DDL statements separated by semicolons
        cur.executescript(SQL_INIT)
    return conn


def _put_mapping(conn: sqlite3.Connection, proto_id: int, ib_id: int) -> None:
    with closing(conn.cursor()) as cur:
        cur.execute(SQL_PUT, (proto_id, ib_id))


def _get_mapping(conn: sqlite3.Connection, proto_id: int) -> Optional[int]:
    with closing(conn.cursor()) as cur:
        cur.execute(SQL_GET, (proto_id,))
        row = cur.fetchone()
        return int(row[0]) if row else None


def _get_simple_order_mapping(conn: sqlite3.Connection, key: str) -> Optional[int]:
    if not key:
        return None
    with closing(conn.cursor()) as cur:
        cur.execute(SQL_SO_GET, (key,))
        row = cur.fetchone()
        return int(row[0]) if row else None


def _put_simple_order_mapping(conn: sqlite3.Connection, key: str, order_id: int) -> None:
    if not key:
        return
    with closing(conn.cursor()) as cur:
        cur.execute(SQL_SO_PUT, (key, order_id))


# Validation

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
        return True


def _validate_qty_price(qty: int, price: float) -> Optional[str]:
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
    if not _within_session():
        return "outside TRADING_HOURS"
    return None


# Envelope format (JSON for now; protobuf planned)
# {
#   "version": "v1",
#   "correlation_id": "...",
#   "msg_type": "SimpleOrder"|"CancelReplaceRequest",
#   "payload": {... or base64 for protobuf}
# }


def _publish_ack(pub: zmq.Socket, correlation_id: str, status: str, reason: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    ack = {"version": "v1", "kind": "Ack", "correlation_id": correlation_id, "status": status, "reason": reason}
    if extra:
        ack.update(extra)
    # JSON ACK
    pub.send_multipart([b"order_acks", json.dumps(ack).encode("utf-8")])
    # Optional protobuf ACK on separate topic
    if PROTO_ACK_MODE and ackpb is not None:
        try:
            m = ackpb.Ack(
                version="v1",
                correlation_id=correlation_id,
                status=status,
                reason=reason,
                order_id=int(ack.get("order_id", 0)) if "order_id" in ack else 0,
            )
            pub.send_multipart([b"order_acks_pb", m.SerializeToString()])
        except Exception:
            # Do not fail path if proto ack fails
            pass
    ack_total.labels(status=status).inc()
    try:
        if reason:
            ack_reason_total.labels(reason=reason[:64]).inc()  # cap label length
        if LAST_RECV_TS is not None:
            ack_latency.observe(max(0.0, time.time() - LAST_RECV_TS))
    except Exception:
        pass


def main() -> None:
    try:
        start_http_server(METRICS_PORT)
        logger.info("Prometheus metrics on :%d", METRICS_PORT)
    except OSError as e:  # Port in use or bind failure should not crash receiver
        logger.warning("Metrics server disabled: %s", e)

    # IB app or dry-run app
    if V1_DRY_RUN:
        logger.warning("Running in V1_DRY_RUN mode: orders will not hit IBKR")
        app = _DryRunApp()
    else:
        app = TradingApp(clientId=21, account=None)

    # Sockets
    ctx = zmq.Context.instance()
    pull = ctx.socket(zmq.PULL)
    rcv_hwm = int(os.getenv("ZMQ_RCVHWM", "10000"))
    pull.setsockopt(zmq.RCVHWM, rcv_hwm)
    pull.bind(ZMQ_ADDR)

    pub = ctx.socket(zmq.PUB)
    snd_hwm = int(os.getenv("ZMQ_SNDHWM", "10000"))
    pub.setsockopt(zmq.SNDHWM, snd_hwm)
    pub.bind(ACK_PUB_ADDR)

    logger.info("V1 receiver bound at %s; ACK PUB at %s", ZMQ_ADDR, ACK_PUB_ADDR)

    conn = _db_conn()

    while True:
        raw = pull.recv()
        # record receive time for latency metrics
        global LAST_RECV_TS
        LAST_RECV_TS = time.time()
        with process_latency.time():
            if PROTO_MODE:
                if envpb is None:
                    reject_total.inc()
                    logger.warning("PROTO mode set but no generated code available")
                    continue
                try:
                    env_msg = envpb.Envelope()
                    env_msg.ParseFromString(raw)
                    version = env_msg.version
                    correlation_id = env_msg.correlation_id
                    msg_type = env_msg.msg_type
                    # Map payload for downstream code
                    if env_msg.HasField("simple_order"):
                        payload = {
                            "symbol": env_msg.simple_order.symbol,
                            "action": env_msg.simple_order.action,
                            "qty": env_msg.simple_order.qty,
                            "order_type": env_msg.simple_order.order_type,
                            "limit_price": env_msg.simple_order.limit_price,
                            "account": env_msg.simple_order.account,
                        }
                    elif env_msg.HasField("cr"):
                        payload = {
                            "proto_id": env_msg.cr.proto_id,
                            "qty": env_msg.cr.qty,
                            "limit_price": env_msg.cr.limit_price,
                            "tif": env_msg.cr.tif,
                        }
                    else:
                        payload = {}
                except Exception:
                    reject_total.inc()
                    logger.warning("Failed to parse protobuf Envelope; dropping")
                    continue
            else:
                try:
                    # Accept both JSON bytes and string
                    txt = raw.decode("utf-8")
                    env = json.loads(txt)
                    env_model = EnvelopeModel(**env)
                except Exception:
                    reject_total.inc()
                    logger.warning("Invalid or non-JSON envelope received; dropping")
                    continue

                version = env_model.version
                correlation_id = env_model.correlation_id
                msg_type = env_model.msg_type
                payload = env_model.payload

            recv_total.inc()

            route_total.labels(msg_type=msg_type).inc()

            if msg_type == "SimpleOrder":
                # Expect payload: {symbol, action, qty, order_type?, limit_price?, account?}
                try:
                    p = SimpleOrderModel(**payload)
                except Exception as e:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", f"bad payload: {e}")
                    continue

                symbol = p.symbol
                action = p.action
                qty = p.qty
                order_type = p.order_type
                limit_price = p.limit_price
                account = p.account or ACCOUNT_ID_DEFAULT
                idemp_key = p.idempotency_key or ""

                if ALLOWED_SYMBOLS is not None and symbol not in ALLOWED_SYMBOLS:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", f"symbol {symbol} not allowed")
                    continue
                price = limit_price if order_type == "LMT" else 1.0
                err = _validate_qty_price(qty, price)
                if err:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", err)
                    continue

                # Idempotency: if key present and known, short-circuit
                existing_order_id = _get_simple_order_mapping(conn, idemp_key) if idemp_key else None
                if existing_order_id is not None:
                    _publish_ack(pub, correlation_id, "ACCEPTED", extra={"order_id": existing_order_id, "idempotent": True})
                    continue

                contract = create_contract(symbol)
                ib_order = make_order(action=action, order_type=order_type, quantity=qty, limit_px=limit_price, account=account)
                try:
                    order_id = app.send_order(contract, ib_order)
                    _put_simple_order_mapping(conn, idemp_key, order_id)
                    _publish_ack(pub, correlation_id, "ACCEPTED", extra={"order_id": order_id})
                except Exception as e:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", f"send failed: {e}")

            elif msg_type == "CancelReplaceRequest":
                # Payload is base64-encoded protobuf bytes, or JSON dict with fields matching cr_pb2
                cr_msg: Optional[cr_pb2.CancelReplaceRequest] = None
                if isinstance(payload, dict):
                    # Build from dict (best-effort)
                    try:
                        cr_msg = cr_pb2.CancelReplaceRequest(
                            proto_id=int(payload.get("proto_id", 0)),
                            qty=int(payload.get("qty", 0)),
                            limit_price=float(payload.get("limit_price", 0)),
                            tif=str(payload.get("tif", "DAY")),
                        )
                    except Exception as e:
                        cr_msg = None
                else:
                    # For now we only support dict; binary support requires base64 decode
                    cr_msg = None

                if cr_msg is None:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", "invalid CancelReplace payload")
                    continue

                proto_id = int(cr_msg.proto_id)
                qty = int(cr_msg.qty)
                price = float(cr_msg.limit_price)

                err = _validate_qty_price(qty, price)
                if err:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", err)
                    continue

                # Resolve existing mapping or create new by placing original if missing
                ib_id = _get_mapping(conn, proto_id)
                try:
                    if ib_id is None:
                        # Submit a fresh order if we don't have mapping
                        symbol = (payload.get("symbol") if isinstance(payload, dict) else None) or os.getenv("ORDER_SYMBOL", "AAPL").upper()
                        if ALLOWED_SYMBOLS is not None and symbol not in ALLOWED_SYMBOLS:
                            reject_total.inc()
                            _publish_ack(pub, correlation_id, "REJECT", f"symbol {symbol} not allowed")
                            continue
                        contract = create_contract(symbol)
                        ib_order = make_order(action="BUY", order_type="LMT", quantity=qty, limit_px=price, account=ACCOUNT_ID_DEFAULT)
                        ib_id = app.send_order(contract, ib_order)
                        _put_mapping(conn, proto_id, ib_id)
                    else:
                        # Replace existing (update qty/price)
                        updated = make_order(action="BUY", order_type="LMT", quantity=qty, limit_px=price, account=ACCOUNT_ID_DEFAULT)
                        app.replace_order(ib_id, updated)
                    _publish_ack(pub, correlation_id, "ACCEPTED", extra={"ib_id": ib_id, "proto_id": proto_id})
                except Exception as e:
                    reject_total.inc()
                    _publish_ack(pub, correlation_id, "REJECT", f"cancel/replace failed: {e}")
            else:
                reject_total.inc()
                _publish_ack(pub, correlation_id, "REJECT", f"unsupported msg_type {msg_type}")


if __name__ == "__main__":
    main()
