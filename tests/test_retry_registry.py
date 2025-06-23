# tests/test_retry_registry.py
from scripts.retry import RetryRegistry
import time

def test_backoff_and_reset():
    reg = RetryRegistry(max_attempts=3, base_delay=0.01)
    key = ("proto1", "AAPL")

    # First two errors → still ready
    assert reg.ready(key) is True
    reg.on_error(key, 500)
    assert reg.ready(key) is True
    reg.on_error(key, 500)
    assert reg.ready(key) is True

     # Third error still allowed (count == max_attempts)
    reg.on_error(key, 500)
    assert reg.ready(key) is True

    # Fourth error exceeds the limit -> NOT ready
    reg.on_error(key, 500)
    assert reg.ready(key) is False

    # wait longer than back-off
    time.sleep(0.02)
    assert reg.ready(key) is True

    # success should reset counter
    reg.on_success(key)
    assert key not in reg._state

