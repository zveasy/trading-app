# manage_orders.py
from scripts.contracts import create_contract
from scripts.orders import create_order
from scripts.core import TradingApp
import time

def execute_limit_order(symbol, qty, limit_price, action="BUY", account=None):
    app = TradingApp(clientId=101)
    contract = create_contract(symbol)
    order = create_order(action, "LMT", qty, limitPrice=limit_price, account=account)
    app.send_order(contract, order)
    time.sleep(5)
    app.disconnect()

if __name__ == "__main__":
    execute_limit_order("AAPL", 10, 190.00, action="BUY", account="personal")
