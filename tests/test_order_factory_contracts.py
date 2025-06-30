from ibapi.order import Order

from scripts.contracts import create_contract
from scripts.order_factory import make_order


def test_make_order_basic():
    o = make_order("BUY", "LMT", 10, limit_px=123.45, account="ACC")
    assert o.action == "BUY"
    assert o.orderType == "LMT"
    assert o.totalQuantity == 10
    assert o.lmtPrice == 123.45
    assert o.account == "ACC"
    assert o.tif == "DAY"
    assert o.eTradeOnly is False
    assert o.firmQuoteOnly is False


def test_make_order_defaults():
    default_order = Order()
    o = make_order("SELL", "MKT", 5)
    assert o.lmtPrice == default_order.lmtPrice
    assert o.account == ""
    assert o.tif == "DAY"


def test_create_contract_defaults():
    c = create_contract("AAPL")
    assert c.symbol == "AAPL"
    assert c.secType == "STK"
    assert c.exchange == "SMART"
    assert c.currency == "USD"
    assert c.primaryExchange == ""
    assert c.tradingClass == ""
    assert c.multiplier == ""


def test_create_contract_with_options():
    c = create_contract(
        "ES",
        secType="FUT",
        exchange="GLOBEX",
        currency="USD",
        primaryExchange="CME",
        lastTradeDateOrContractMonth="202406",
        tradingClass="ES",
        multiplier="50",
    )
    assert c.primaryExchange == "CME"
    assert c.lastTradeDateOrContractMonth == "202406"
    assert c.tradingClass == "ES"
    assert c.multiplier == "50"
