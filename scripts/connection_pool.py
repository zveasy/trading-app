#!/usr/bin/env python3
"""
scripts.connection_pool
──────────────────────
A simple thread-safe connection pool for TradingApp (Interactive Brokers).

• Maintains a pool of reusable TradingApp instances keyed by (host, port, clientId, account)
• Thread-safe checkout and return.
• Auto-creates new TradingApp if none available for requested key.
• Handles pool size limits and optional cleanup.

Usage:
    from scripts.connection_pool import ConnectionPool
    pool = ConnectionPool(maxsize=5)

    # Get a connection for a specific host/port/clientId/account
    app = pool.acquire("127.0.0.1", 7497, 1, "DUH148810")
    ...  # use app (TradingApp)
    pool.release(app)
"""

import threading
from queue import Queue, Empty
from typing import Tuple, Optional, Dict, List
from scripts.core import TradingApp

PoolKey = Tuple[str, int, int, Optional[str]]

class ConnectionPool:
    def __init__(self, maxsize: int = 5):
        self._lock = threading.Lock()
        self._maxsize = maxsize
        self._pool: Dict[PoolKey, List[TradingApp]] = {}
        self._total_count = 0

    def _make_key(self, host: str, port: int, clientId: int, account: Optional[str]) -> PoolKey:
        return (host, port, clientId, account)

    def acquire(self, host: str, port: int, clientId: int, account: Optional[str]) -> TradingApp:
        key = self._make_key(host, port, clientId, account)
        with self._lock:
            conns = self._pool.setdefault(key, [])
            if conns:
                return conns.pop()
            if self._total_count < self._maxsize:
                app = TradingApp(host=host, port=port, clientId=clientId, account=account)
                self._total_count += 1
                return app
            raise RuntimeError("No connections available in pool (maxsize reached)")

    def release(self, app: TradingApp):
        key = self._make_key(app.wrapper.host, app.wrapper.port, app.wrapper.clientId, getattr(app, "account", None))
        with self._lock:
            self._pool.setdefault(key, []).append(app)

    def close_all(self):
        with self._lock:
            for conn_list in self._pool.values():
                for app in conn_list:
                    try:
                        app.disconnect()
                    except Exception:
                        pass
            self._pool.clear()
            self._total_count = 0
