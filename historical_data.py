import yfinance as yf

def fetch_historical_data(ticker, period="2d", interval="5m"):
    data = yf.download(ticker, period=period, interval=interval)
    return data

if __name__ == "__main__":
    df = fetch_historical_data("AAPL", period="1d", interval="5m")
    print(df)
