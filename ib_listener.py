import zmq
import json
import time
from core import TradingApp, create_contract, create_order
from utils import setup_logger

logger = setup_logger(name="IBListener", log_file="ib_listener.log")

# ZMQ socket setup
ctx = zmq.Context()
socket = ctx.socket(zmq.PULL)
socket.bind("tcp://*:5555")

logger.info("✅ IBTrader ZMQ listener started on port 5555...")

# Risk profile → IB account mapping
account_map = {
    "HIGH": "DUH148810",
    "MEDIUM": "DUH148811",
    "LOW": "DUH148812",
    "SMART_BETA": "DUH148813",
    "EXPERIMENTAL": "DUH148814"
}

# Initialize IB connection
app = TradingApp(clientId=11, account=None)  # account set dynamically per trade

while True:
    try:
        msg = socket.recv_json()
        action = msg.get('action', '').upper()
        symbol = msg.get('symbol')
        qty = msg.get('qty')
        strategy = msg.get('strategy', 'unknown')
        risk_profile = msg.get('risk_profile', 'EXPERIMENTAL').upper()
        ts = msg.get('timestamp', int(time.time()))

        if not symbol or not action or not qty:
            logger.warning(f"⚠️ Invalid trade message received: {msg}")
            continue

        account_id = account_map.get(risk_profile, "DUH148814")

        logger.info(f"📥 Signal [{risk_profile}] from {strategy} → {action} {symbol} x{qty} @ {ts} (Account: {account_id})")

        # Build contract & order
        contract = create_contract(symbol)
        order = create_order(action, orderType="MKT", quantity=qty, account=account_id)

        # Send trade
        order_id = app.send_order(contract, order)
        logger.info(f"✅ Order #{order_id} placed: {action} {symbol} x{qty} in {account_id}")

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
