# portfolio.py
from scripts.core import TradingApp
import time

def get_portfolio():
    app = TradingApp(clientId=103)
    app.request_portfolio()
    time.sleep(5)
    portfolio = app.portfolio
    app.disconnect()
    return portfolio

if __name__ == "__main__":
    portfolio = get_portfolio()
    print("📊 Portfolio Details:")
    for item in portfolio:
        print(item)
