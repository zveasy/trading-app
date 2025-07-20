import pytest
from freezegun import freeze_time

from risk.throttle import (
    Throttle,
    ThrottleException,
    ContractSpec,
    throttle_blocked_total,
)


def test_block_and_reset():
    t = Throttle(max_orders_per_sec=2, max_notional=100)

    c = ContractSpec(symbol="AAPL")

    with freeze_time("2024-01-01 00:00:00") as frozen:
        t.block_if_needed(c, 1, 40)
        t.block_if_needed(c, 1, 40)
        assert throttle_blocked_total._value.get() == 0

        with pytest.raises(ThrottleException):
            t.block_if_needed(c, 1, 10)
        assert throttle_blocked_total._value.get() == 1

        frozen.tick(1.1)
        t.block_if_needed(c, 1, 10)

        with pytest.raises(ThrottleException):
            t.block_if_needed(c, 2, 60)
        assert throttle_blocked_total._value.get() == 2
