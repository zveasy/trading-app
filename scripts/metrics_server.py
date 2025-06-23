#!/usr/bin/env python3
"""
Prometheus metrics registry for the Cancel/Replace stack.
Import the symbols you need and call `start()` once at process-boot.
"""

from prometheus_client import Counter, Gauge, start_http_server

# ── Core counters ───────────────────────────────────────────────────────────
RECEIVER_MSGS     = Counter("receiver_msgs_total", "Total protobuf messages received")
RECEIVER_ERRORS   = Counter("receiver_errors_total", "Total errors seen in receiver loop")
IB_RETRIES        = Counter("ib_retries_total", "Total retry-backoff attempts (IB errors)")
RECEIVER_BACKOFFS = Counter("receiver_backoff_total", "Dropped messages while still backing off")
RETRY_RESETS      = Counter("retry_reset_total", "Times a key’s back-off window was cleared")

# ── Gauges ───────────────────────────────────────────────────────────────────
INFLIGHT_CONN     = Gauge("inflight_ib_connections", "Open IB Gateway/TWS connections")

# ── Start helper ─────────────────────────────────────────────────────────────
def start(port: int = 9100) -> None:
    """
    Launch a WSGI server on the given port (default 9100).
    Safe to call multiple times – subsequent calls are ignored.
    """
    try:
        # If already started this will raise OSError; swallow it.
        start_http_server(port)
    except OSError:
        pass
