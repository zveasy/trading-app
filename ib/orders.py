# orders.py
from ibapi.order import Order

BUY = "BUY"
SELL = "SELL"

def market(action="BUY", quantity=1, account=None, tif="DAY", outsideRTH=False):
    order = Order()
    order.action = action
    order.orderType = "MKT"
    order.totalQuantity = quantity
    order.tif = tif
    order.outsideRth = outsideRTH
    order.transmit = True
    order.eTradeOnly = False
    order.firmQuoteOnly = False
    if account:
        order.account = account
    return order

def limit(action="BUY", quantity=1, limit_price=0.0, account=None, tif="DAY", outsideRTH=False):
    order = Order()
    order.action = action
    order.orderType = "LMT"
    order.lmtPrice = limit_price
    order.totalQuantity = quantity
    order.tif = tif
    order.outsideRth = outsideRTH
    order.transmit = True
    if account:
        order.account = account
    return order

def stop(action="SELL", quantity=1, stop_price=0.0, account=None, tif="DAY", outsideRTH=False):
    order = Order()
    order.action = action
    order.orderType = "STP"
    order.auxPrice = stop_price
    order.totalQuantity = quantity
    order.tif = tif
    order.outsideRth = outsideRTH
    order.transmit = True
    if account:
        order.account = account
    return order

def stop_limit(action="SELL", quantity=1, stop_price=0.0, limit_price=0.0, account=None, tif="DAY", outsideRTH=False):
    order = Order()
    order.action = action
    order.orderType = "STP LMT"
    order.auxPrice = stop_price
    order.lmtPrice = limit_price
    order.totalQuantity = quantity
    order.tif = tif
    order.outsideRth = outsideRTH
    order.transmit = True
    if account:
        order.account = account
    return order

# Default create_order fallback
def create_order(action="BUY", orderType="MKT", quantity=1, account=None):
    return market(action, quantity, account)
