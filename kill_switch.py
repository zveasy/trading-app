#!/usr/bin/env python3
"""Redis-backed kill switch monitor."""

from __future__ import annotations

import os
import signal
import time
from typing import Optional

import redis
from prometheus_client import Counter

from scripts.core import TradingApp


kill_switch_activations_total = Counter(
    "kill_switch_activations_total", "Times the kill switch has triggered"
)

_SHUTDOWN = False


def _request_shutdown(_sig: int, _frm) -> None:
    global _SHUTDOWN
    _SHUTDOWN = True


def monitor(
    app: TradingApp,
    *,
    redis_url: Optional[str] = None,
    poll_s: Optional[float] = None,
) -> None:
    """Poll Redis for the ``KILL_SWITCH`` key and liquidate positions when set."""

    poll_interval = poll_s or float(os.getenv("KILL_SWITCH_POLL_S", "5"))
    r = redis.Redis.from_url(redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    while not _SHUTDOWN:
        try:
            val = r.get("KILL_SWITCH")
        except Exception:
            val = None

        if val and val.decode().upper() == "TRUE":
            kill_switch_activations_total.inc()
            app.close_all_positions()
            break

        time.sleep(poll_interval)

    try:
        app.disconnect()
    except Exception:
        pass

