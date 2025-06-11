# yahoo_data.py
import yfinance as yf
import pandas as pd
import sqlite3

def fetch_historical(ticker, period="7d", interval="1h"):
    ticker_data = yf.Ticker(ticker)
    data = ticker_data.history(period=period, interval=interval)
    return data

def store_to_sqlite(df, ticker):
    conn = sqlite3.connect("yahoo_data.sqlite")
    df.to_sql(f"{ticker}_historical", conn, if_exists="replace")
    conn.close()

if __name__ == "__main__":
    df = fetch_historical("AAPL", period="5d", interval="15m")
    if not df.empty:
        store_to_sqlite(df, "AAPL")
        print(df.tail())
    else:
        print("Data fetch was unsuccessful. Try again shortly.")
