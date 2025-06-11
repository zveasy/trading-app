# contracts.py
from ibapi.contract import Contract

def create_contract(symbol, secType="STK", exchange="SMART", currency="USD",
                    primaryExchange=None, lastTradeDateOrContractMonth=None,
                    tradingClass=None, multiplier=None):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = secType
    contract.exchange = exchange
    contract.currency = currency

    if primaryExchange:
        contract.primaryExchange = primaryExchange
    if lastTradeDateOrContractMonth:
        contract.lastTradeDateOrContractMonth = lastTradeDateOrContractMonth
    if tradingClass:
        contract.tradingClass = tradingClass
    if multiplier:
        contract.multiplier = multiplier

    return contract

def stock(symbol, exchange, currency, primaryExchange=None):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.exchange = exchange
    contract.currency = currency
    if primaryExchange:
        contract.primaryExchange = primaryExchange
    return contract

def future(symbol, exchange, contract_month):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "FUT"
    contract.exchange = exchange
    contract.currency = "USD"
    contract.lastTradeDateOrContractMonth = contract_month
    return contract

def option(symbol, exchange, contract_month, strike, right, currency="USD", multiplier="100"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "OPT"
    contract.exchange = exchange
    contract.currency = currency
    contract.lastTradeDateOrContractMonth = contract_month
    contract.strike = strike
    contract.right = right  # 'C' for Call, 'P' for Put
    contract.multiplier = multiplier
    return contract

def etf(symbol, exchange="SMART", currency="USD", primaryExchange="ARCA"):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"  # ETFs are technically stocks
    contract.exchange = exchange
    contract.currency = currency
    contract.primaryExchange = primaryExchange
    return contract

def bond(cusip, exchange="SMART"):
    contract = Contract()
    contract.secType = "BOND"
    contract.symbol = ""
    contract.exchange = exchange
    contract.currency = "USD"
    contract.cusip = cusip
    return contract

def commodity(symbol, exchange, contract_month):
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "FUT"
    contract.exchange = exchange
    contract.currency = "USD"
    contract.lastTradeDateOrContractMonth = contract_month
    return contract



#✅ Common Commodity Symbols
# Symbol	Commodity	Exchange
# CL	    Crude Oil	NYMEX
# GC	    Gold	    COMEX
# SI	    Silver	    COMEX
# NG	    Natural Gas	NYMEX
# ZC	    Corn	    CBOT
# ZW	    Wheat	    CBOT
# ZS	    Soybeans	CBOT
