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
