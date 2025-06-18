#!/usr/bin/env python3
"""
helpers.py
══════════
Small, reusable helper utilities shared across trading-app scripts.

Current contents
----------------
• wait_order_active()  – Poll the in-memory `order_statuses` cache inside
  a TradingApp-like object until an order reaches a target state.

The helper is *framework-agnostic*: anything that exposes
`order_statuses: Dict[int, Dict[str, Any]]` will work (real TradingApp or
a FakeApp in unit-tests).
"""

from __future__ import annotations

import time
from typing import Dict, Any, Iterable, Sequence


# --------------------------------------------------------------------------- #
# Helper: wait until an IB order is in a given state                          #
# --------------------------------------------------------------------------- #
def wait_order_active(
    app: "HasOrderStatuses",
    ib_order_id: int,
    *,
    ok_states: Sequence[str] | None = None,
    timeout: float = 5.0,
    poll_interval: float = 0.25,
) -> bool:
    """
    Block (polling) until *ib_order_id* moves into one of *ok_states*.

    Parameters
    ----------
    app : HasOrderStatuses
        Any object exposing ``order_statuses: Dict[int, Dict[str, Any]]``
        where each value maps at least the key ``"status" -> str``.
    ib_order_id : int
        The Interactive Brokers order-id we’re watching.
    ok_states : Sequence[str] | None, default ('Submitted','PreSubmitted')
        Collection of order-status strings considered *active* enough to
        continue.  If *None*, defaults to the common active states.
    timeout : float, default 5.0
        Maximum seconds to wait before giving up.
    poll_interval : float, default 0.25
        Sleep interval between polls (seconds).

    Returns
    -------
    bool
        ``True`` if the order reached one of *ok_states* within *timeout*,
        else ``False``.
    """
    if ok_states is None:
        ok_states = ("Submitted", "PreSubmitted")

    deadline = time.time() + timeout

    while time.time() < deadline:
        info: Dict[str, Any] | None = app.order_statuses.get(ib_order_id)
        if info and info.get("status") in ok_states:
            return True
        time.sleep(poll_interval)

    return False


# --------------------------------------------------------------------------- #
# Protocol-like hint (avoids importing typing_extensions.Protocol)            #
# --------------------------------------------------------------------------- #
class HasOrderStatuses:
    """Minimal structural type for mypy / type-checkers."""
    order_statuses: Dict[int, Dict[str, Any]]
