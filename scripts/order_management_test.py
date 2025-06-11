from scripts.core import TradingApp
from scripts.contracts import create_contract
from scripts.orders import create_order
import time
import logging

logging.basicConfig(level=logging.INFO)

def test_order_lifecycle():
    app = TradingApp(clientId=12)
    time.sleep(2)  # Wait for connection

    contract = create_contract("AAPL")
    
    print("\n📦 Sending initial limit order...")
    order = create_order("BUY", "LMT", quantity=10, limit_price=185.00)
    order_id = app.send_order(contract, order)
    print(f"✅ Order sent with ID: {order_id}")

    time.sleep(3)

    print("\n❌ Canceling the order...")
    app.cancel_order_by_id(order_id)
    time.sleep(2)

    print("\n🔄 Updating order with new limit price...")
    new_order = create_order("BUY", "LMT", quantity=10, limit_price=187.50)
    app.update_order(contract, new_order, order_id)
    time.sleep(3)

    print("\n🚫 Canceling all orders...")
    app.cancel_all_orders()
    time.sleep(2)

    print("\n🔌 Disconnecting...")
    app.disconnect()

if __name__ == "__main__":
    test_order_lifecycle()
