# positions.py
from core import TradingApp
import time

def get_positions():
    app = TradingApp(clientId=102)
    app.request_positions()
    time.sleep(5)  # Wait for data
    positions = app.positions
    app.disconnect()
    return positions

if __name__ == "__main__":
    positions = get_positions()
    print("📌 Current Positions:")
    for position in positions:
        print(position)
