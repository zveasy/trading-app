from scripts.connection_pool import ConnectionPool
from scripts.core import TradingApp

def test_connection_pool_acquire_and_release():
    pool = ConnectionPool(maxsize=2)

    # Acquire first connection
    app1 = pool.acquire("127.0.0.1", 7497, 1, "TEST")
    assert isinstance(app1, TradingApp)

    # Acquire second connection
    app2 = pool.acquire("127.0.0.1", 7497, 2, "TEST")
    assert isinstance(app2, TradingApp)

    # Try acquiring third should fail (pool size is 2)
    try:
        pool.acquire("127.0.0.1", 7497, 3, "TEST")
        assert False, "Expected RuntimeError when pool is exhausted"
    except RuntimeError:
        pass

    # Release one connection and re-acquire (should reuse)
    pool.release(app1)
    app3 = pool.acquire("127.0.0.1", 7497, 1, "TEST")
    assert app3 is app1  # Should get the same instance back

    # Clean up
    pool.release(app2)
    pool.release(app3)
    pool.close_all()
    
print("ConnectionPool test passed!")