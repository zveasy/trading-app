import socket
import time

import pytest

from scripts.contracts import create_contract
from scripts.core import TradingApp
from scripts.metrics_server import ib_connection_status
from scripts.order_factory import make_order

IB_HOST = "127.0.0.1"
IB_PORT = 4002


def _has_ib_mock() -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect((IB_HOST, IB_PORT))
    except OSError:
        return False
    finally:
        s.close()
    return True


def test_reconnect_and_flush():
    if not _has_ib_mock():
        pytest.skip("ib-mock not running")

    app = TradingApp(host=IB_HOST, port=IB_PORT, clientId=98)
    contract = create_contract("AAPL")
    order = make_order("BUY", "MKT", 1)

    first = app.send_order(contract, order)
    assert ib_connection_status._value.get() == 1

    app.disconnect()
    time.sleep(0.5)

    second = app.send_order(contract, order)
    assert second != first
    assert len(app._order_buffer) == 1

    for _ in range(10):
        if ib_connection_status._value.get() == 1:
            break
        time.sleep(1)

    assert ib_connection_status._value.get() == 1
    assert len(app._order_buffer) == 0
    app.disconnect()
