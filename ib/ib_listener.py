import os
import zmq
import json
import time
from typing import Optional, Set
from dotenv import load_dotenv
from prometheus_client import Counter, start_http_server
from scripts.core import TradingApp, create_contract, create_order
from utils.utils import setup_logger

load_dotenv()
logger = setup_logger(name="IBListener", log_file="ib_listener.log")

# ZMQ socket setup (bind to localhost by default for safety)
ZMQ_ADDR = os.getenv("ZMQ_ADDR", "tcp://127.0.0.1:5555")
ACK_PUB_ADDR = os.getenv("ACK_PUB_ADDR", "tcp://127.0.0.1:6001")
ctx = zmq.Context()
socket = ctx.socket(zmq.PULL)
# Apply high-water mark to avoid unbounded memory
rcv_hwm = int(os.getenv("ZMQ_RCVHWM", "10000"))
socket.setsockopt(zmq.RCVHWM, rcv_hwm)
socket.bind(ZMQ_ADDR)

# Optional ACK publisher for JSON listener (topic: json_order_acks)
ack_pub = ctx.socket(zmq.PUB)
snd_hwm = int(os.getenv("ZMQ_SNDHWM", "10000"))
ack_pub.setsockopt(zmq.SNDHWM, snd_hwm)
ack_pub.bind(ACK_PUB_ADDR)

logger.info(f"✅ IBTrader ZMQ listener bound to {ZMQ_ADDR}; ACK PUB at {ACK_PUB_ADDR}")

# Risk profile → IB account mapping
account_map = {
    "HIGH": "DUH148810",
    "MEDIUM": "DUH148811",
    "LOW": "DUH148812",
    "SMART_BETA": "DUH148813",
    "EXPERIMENTAL": "DUH148814"
}

def _parse_symbols_env() -> Optional[Set[str]]:
    raw = os.getenv("ALLOWED_SYMBOLS", "").strip()
    if not raw:
        return None
    return {s.strip().upper() for s in raw.split(",") if s.strip()}


ALLOWED_SYMBOLS = _parse_symbols_env()

# Initialize IB connection
app = TradingApp(clientId=11, account=None)  # account set dynamically per trade

# Metrics
METRICS_PORT = int(os.getenv("METRICS_PORT", "9101"))
_recv_total = Counter("json_listener_received_total", "Total inbound JSON trade messages")
_reject_total = Counter("json_listener_rejected_total", "Total rejected JSON trade messages")
_sent_total = Counter("json_listener_orders_sent_total", "Total orders submitted from JSON listener")
start_http_server(METRICS_PORT)
logger.info("Prometheus metrics server started on :%d", METRICS_PORT)

while True:
    try:
        msg = socket.recv_json()
        action = msg.get('action', '').upper()
        symbol = msg.get('symbol')
        qty = msg.get('qty')
        strategy = msg.get('strategy', 'unknown')
        risk_profile = msg.get('risk_profile', 'EXPERIMENTAL').upper()
        ts = msg.get('timestamp', int(time.time()))

        _recv_total.inc()
        # Basic validation
        if not symbol or not isinstance(symbol, str):
            _reject_total.inc()
            logger.warning(f"⚠️ Invalid symbol in message: {msg}")
            continue
        symbol = symbol.upper().strip()
        if action not in ("BUY", "SELL"):
            _reject_total.inc()
            logger.warning(f"⚠️ Invalid action in message: {msg}")
            continue
        try:
            qty = int(qty)
        except Exception:
            _reject_total.inc()
            logger.warning(f"⚠️ Invalid qty in message: {msg}")
            continue
        if qty <= 0:
            _reject_total.inc()
            logger.warning(f"⚠️ Non-positive qty in message: {msg}")
            continue
        if ALLOWED_SYMBOLS is not None and symbol not in ALLOWED_SYMBOLS:
            _reject_total.inc()
            logger.warning(f"🚫 Symbol {symbol} not in ALLOWED_SYMBOLS; dropping")
            continue

        account_id = account_map.get(risk_profile, "DUH148814")

        logger.info(f"📥 Signal [{risk_profile}] from {strategy} → {action} {symbol} x{qty} @ {ts} (Account: {account_id})")

        # Build contract & order then send via TradingApp helper
        contract = create_contract(symbol)
        order = create_order(action, orderType="MKT", quantity=qty, account=account_id)
        order_id = app.send_order(contract, order)
        _sent_total.inc()
        logger.info(f"📨 Sent order #{order_id}: {action} {qty} {symbol} type=MKT profile={risk_profile} account={account_id}")

        # Publish basic ACK if correlation_id present
        corr_id = msg.get("correlation_id") or msg.get("id") or ""
        if corr_id:
            ack = {
                "kind": "JsonOrderAck",
                "correlation_id": corr_id,
                "symbol": symbol,
                "action": action,
                "qty": qty,
                "status": "ACCEPTED",
            }
            ack_pub.send_multipart([b"json_order_acks", json.dumps(ack).encode("utf-8")])

        # Optional: pull live account/position info after each trade
        time.sleep(1)
        portfolio = app.request_portfolio()
        logger.info(f"💼 Net Liquidation: {portfolio.get('NetLiquidation')}")

        positions = app.request_positions()
        for sym, pos in positions.items():
            logger.info(f"📈 {sym} -> Pos: {pos['position']} | Price: {pos['market_price']} | PnL: {pos['unrealized_pnl']}")

        print("------------------------------------------------------------")

    except KeyboardInterrupt:
        break
    except Exception as e:
        logger.error(f"❌ Exception during trade loop: {str(e)}")

app.disconnect()
logger.info("🔌 Disconnected from IB.")
