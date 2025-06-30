from scripts.orders import market, limit, stop, stop_limit, create_order


def test_market_defaults():
    o = market()
    assert o.orderType == "MKT"
    assert o.action == "BUY"
    assert o.totalQuantity == 1
    assert o.tif == "DAY"
    assert o.outsideRth is False
    assert o.eTradeOnly is False
    assert o.firmQuoteOnly is False


def test_limit_price_and_account():
    o = limit("SELL", 5, limit_price=123.45, account="ACC")
    assert o.orderType == "LMT"
    assert o.action == "SELL"
    assert o.lmtPrice == 123.45
    assert o.totalQuantity == 5
    assert o.account == "ACC"


def test_stop_order():
    o = stop(quantity=2, stop_price=42.0)
    assert o.orderType == "STP"
    assert o.auxPrice == 42.0
    assert o.totalQuantity == 2


def test_stop_limit():
    o = stop_limit(quantity=3, stop_price=10.0, limit_price=10.5)
    assert o.orderType == "STP LMT"
    assert o.auxPrice == 10.0
    assert o.lmtPrice == 10.5
    assert o.totalQuantity == 3


def test_create_order_fallback():
    o = create_order("BUY", "LMT", 7, limit_price=99.0, account="ACC")
    assert o.action == "BUY"
    assert o.orderType == "LMT"
    assert o.totalQuantity == 7
    assert o.lmtPrice == 99.0
    assert o.account == "ACC"


