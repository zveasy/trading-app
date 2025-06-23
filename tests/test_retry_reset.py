import time
from scripts.retry import RetryRegistry, SHOULD_RETRY

def test_backoff_resets_on_success():
    r = RetryRegistry(base_delay=0.1, max_attempts=1, max_delay=0.1)
    k = (100, "AAPL")

    assert r.ready(k)

    # simulate error → not ready
    r.on_error(k, next(iter(SHOULD_RETRY)))
    assert not r.ready(k)

    # wait enough time, still not ready until delay passes
    time.sleep(0.05)
    assert not r.ready(k)

    # mark success → instant reset
    r.on_success(k)
    assert r.ready(k)

