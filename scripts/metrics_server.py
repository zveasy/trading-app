#!/usr/bin/env python3
"""
Prometheus metrics registry for the Cancel/Replace stack.
Import the symbols you need and call `start()` once at process-boot.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# ── Core counters ───────────────────────────────────────────────────────────
RECEIVER_MSGS = Counter("receiver_msgs_total", "Total protobuf messages received")
RECEIVER_ERRORS = Counter("receiver_errors_total", "Total errors seen in receiver loop")
IB_RETRIES = Counter("ib_retries_total", "Total retry-backoff attempts (IB errors)")
IB_ERROR_CODES = Counter("ib_error_codes_total", "IB errors by code", ["code"])
RECEIVER_BACKOFFS = Counter(
    "receiver_backoff_total", "Dropped messages while still backing off"
)
RETRY_RESETS = Counter("retry_reset_total", "Times a key’s back-off window was cleared")

# Orders by symbol
orders_by_symbol = Counter("receiver_orders_by_symbol", "Orders by symbol", ["symbol"])

# Orders by type
orders_by_type = Counter("receiver_orders_by_type", "Orders by order type", ["type"])

# Order latency
order_latency = Histogram(
    "receiver_order_latency_seconds", "Order processing latency", ["symbol"]
)

# Queue depth (if you have an async queue)
queue_depth = Gauge("receiver_queue_depth", "Number of orders waiting in queue")

# Orders filled/canceled/rejected
orders_filled = Counter("receiver_orders_filled_total", "Total filled orders")
orders_canceled = Counter("receiver_orders_canceled_total", "Total canceled orders")
orders_rejected = Counter("receiver_orders_rejected_total", "Total rejected orders")
throttle_blocked_total = Counter("throttle_blocked_total", "Orders blocked by throttle")


# ── Gauges ───────────────────────────────────────────────────────────────────
INFLIGHT_CONN = Gauge("inflight_ib_connections", "Open IB Gateway/TWS connections")


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
