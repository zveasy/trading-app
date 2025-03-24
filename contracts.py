# contracts.py
from ibapi.contract import Contract

def create_contract(symbol, secType="STK", exchange="SMART", currency="USD", primaryExchange=None):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = secType
    contract.exchange = exchange
    contract.currency = currency

    if primaryExchange:
        contract.primaryExchange = primaryExchange

    return contract

# 📈 Stocks
def stock(symbol, exchange="SMART", currency="USD", primaryExchange=None):
    return create_contract(symbol, secType="STK", exchange=exchange, currency=currency, primaryExchange=primaryExchange)

# 📉 Futures (including commodities)
def future(symbol, exchange="NYMEX", contract_month="202405", currency="USD"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "FUT"
    contract.exchange = exchange
    contract.currency = currency
    contract.lastTradeDateOrContractMonth = contract_month
    return contract

# 💰 Options
def option(symbol, exchange="SMART", contract_month="20240419", strike=100, right="C", currency="USD"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "OPT"
    contract.exchange = exchange
    contract.currency = currency
    contract.lastTradeDateOrContractMonth = contract_month
    contract.strike = strike
    contract.right = right  # 'C' for call, 'P' for put
    return contract

# 🌾 Commodities (Wrapper over future)
def commodity(symbol, contract_month, exchange="NYMEX", currency="USD"):
    return future(symbol=symbol, exchange=exchange, contract_month=contract_month, currency=currency)
