# trading-app/scripts/order_factory.py
from typing import Optional
from ibapi.order import Order

def make_order(
    action: str,
    order_type: str,
    quantity: int,
    limit_px: Optional[float] = None,
    account: Optional[str] = None,
) -> Order:
    """
    Return a CLEAN IB Order object with the most common fields set and
    troublesome flags stripped.
    """
    o = Order()
    o.action        = action           # "BUY" / "SELL"
    o.orderType     = order_type       # "LMT", "MKT", …
    o.totalQuantity = quantity
    o.tif           = "DAY"

    # Optional limit price
    if limit_px is not None:
        o.lmtPrice = limit_px

    # Optional account assignment
    if account:
        o.account = account

    # ---- strip flags that cause 10268 / 10269 at IB -----------------------
    for flag in ("eTradeOnly", "firmQuoteOnly", "mifid2Affiliated"):
        if hasattr(o, flag):
            setattr(o, flag, False)

    return o
