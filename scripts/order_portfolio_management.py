# order_portfolio_management.py
import time
from scripts.contracts import create_contract
from scripts.orders import create_order
from scripts.core import TradingApp

# === Managing Orders Once They're Placed ===
def test_order_lifecycle():
    app = TradingApp(clientId=12)

    # Create and send an initial limit order
    print("\n\U0001F4E6 Sending initial limit order...")
    contract = create_contract("AAPL")
    order_1 = create_order("BUY", "LMT", 10, limit_price=185.00)
    order_id = app.send_order(contract, order_1)
    print(f"\u2705 Order sent with ID: {order_id}")
    time.sleep(2)

    # Cancel the order
    print("\n\u274C Canceling the order...")
    app.cancel_order_by_id(order_id)
    time.sleep(2)

    # Update the order with a new limit price
    print("\n\U0001F501 Updating order with new limit price...")
    order_2 = create_order("BUY", "LMT", 10, limit_price=187.50)
    app.update_order(contract, order_2, order_id)
    time.sleep(2)

    # Cancel all orders
    print("\n\u274C Canceling all orders...")
    app.cancel_all_orders()
    time.sleep(2)

    print("\n\ud83d\udc90 Disconnecting...")
    app.disconnect()

# === Getting Portfolio Details ===
def test_portfolio_data():
    print("\n\U0001F4CA Fetching portfolio details...")
    app = TradingApp(clientId=13)
    time.sleep(2)

    values = app.get_account_values()
    for k, v in list(values.items())[:15]:  # print sample
        print(f"{k}: {v}")

    net_liquidation = app.get_account_values("NetLiquidation")
    print(f"\nNet Liquidation Value: {net_liquidation}")

    print("\n\ud83d\udc90 Disconnecting...")
    app.disconnect()

if __name__ == "__main__":
    test_order_lifecycle()
    test_portfolio_data()
