"""
scripts.metrics_server
––––––––––––––––––––––
Exports Prometheus metrics on :9100 (default).

Import in any module:
    from scripts.metrics_server import (
        start as start_metrics,
        RECEIVER_MSGS, RECEIVER_ERRORS, IB_RETRIES, INFLIGHT_CONN
    )
"""
from prometheus_client import Counter, Gauge, start_http_server

# ───────────────────────── Counters ──────────────────────────────────────
RECEIVER_MSGS   = Counter("receiver_msgs_total",   "Total messages received")
RECEIVER_ERRORS = Counter("receiver_errors_total", "Total receiver errors")
IB_RETRIES      = Counter("ib_retries_total",      "IB retry attempts")

# ───────────────────────── Gauges ────────────────────────────────────────
INFLIGHT_CONN   = Gauge("inflight_ib_connections", "Open IB API connections")

# ───────────────────────── Helper ────────────────────────────────────────
def start(port: int = 9100) -> None:
    """
    Spin up the Prometheus HTTP exporter (non-blocking).
    Call exactly once per process (subsequent calls are no-ops).
    """
    start_http_server(port)
