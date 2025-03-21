# orders.py
from ibapi.order import Order

def create_order(action="BUY", orderType="MKT", quantity=1, account=None):
    order = Order()
    order.action = action
    order.orderType = orderType
    order.totalQuantity = quantity
    order.transmit = True
    order.eTradeOnly = False
    order.firmQuoteOnly = False

    if account:
        order.account = account

    return order
