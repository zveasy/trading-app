#!/usr/bin/env python3
"""
scripts.helpers
────────────────
Utility helpers shared by multiple scripts.
"""

from __future__ import annotations
import time
from typing import Collection, Dict, Any

# We do a *local import* inside the function to avoid circular-importing
# TradingApp at module-load time.
DEFAULT_ACTIVE_STATUSES: tuple[str, ...] = ("Submitted", "PreSubmitted")


def wait_order_active(
    app,                       # `scripts.core.TradingApp`
    ib_id: int,
    timeout: float = 5.0,
    active_states: Collection[str] = DEFAULT_ACTIVE_STATUSES,
) -> bool:
    """
    Spin-wait until the given `ib_id` moves into an *active* state
    (Submitted / PreSubmitted by default).  
    Returns **True** if the state is reached within `timeout`, else **False**.

    Parameters
    ----------
    app : scripts.core.TradingApp
        An already-connected TradingApp instance.
    ib_id : int
        The Interactive Brokers orderId to monitor.
    timeout : float, optional
        Seconds to wait before giving up (default 5.0 s).
    active_states : Collection[str], optional
        A custom iterable of states that count as *active*.

    Notes
    -----
    • Reads `app.order_statuses`, which is a
      `Dict[int, Dict[str, Any]]` populated in `core.TradingApp.orderStatus`.
    • Sleeps 100 ms between polls to avoid busy-waiting.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        info: Dict[str, Any] | None = app.order_statuses.get(ib_id)
        if info and info.get("status") in active_states:
            return True
        time.sleep(0.1)
    return False
