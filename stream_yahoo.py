import yfinance as yf
import time

def stream_price(ticker, interval_seconds=60, duration_minutes=10):
    end_time = time.time() + duration_minutes * 60
    while time.time() < end_time:
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period='1m')
        last_quote = data['Close'].iloc[-1]
        print(f"{ticker} latest price: {last_quote}")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    stream_price("AAPL", interval_seconds=60, duration_minutes=5)
