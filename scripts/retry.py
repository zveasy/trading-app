#!/usr/bin/env python3
"""
RetryRegistry
─────────────
A small helper that throttles re-processing of a (proto_id, symbol) key
after we receive *retry-worthy* Interactive Brokers error codes.

Key features
============
* Exponential back-off with a capped maximum delay.
* Automatic reset of back-off once we observe a SUCCESS for that key.
* Thread-safe (using ``threading.Lock``).
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple


# IB error codes that are worth retrying (extend as needed)
SHOULD_RETRY = {
    1100,   # Connectivity lost
    1101,   # Connectivity restored – session reset
    200,    # No security definition found
    202,    # Order cancelled (but we still need to place a new one)
    104,    # Cannot modify a filled order (usually transient)
}

Key = Tuple[int, str]  # (proto_id, sym)


class RetryRegistry:
    """
    Tracks the *next allowed time* a key may be processed again.

    Parameters
    ----------
    max_attempts : int
        Number of exponential steps before we clamp at ``max_delay``.
    base_delay : float
        The initial delay in **seconds** (step 0 → 1).
    max_delay : float
        Upper bound for back-off delay in **seconds**.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 4,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay   = base_delay
        self.max_delay    = max_delay

        self._lock  = threading.Lock()
        # key → (next_allowed_ts, attempt_idx)
        self._state: Dict[Key, Tuple[float, int]] = {}

    # ───────────────────────────────────────────────────────────
    # Public helpers
    # ───────────────────────────────────────────────────────────
    def ready(self, key: Key) -> bool:
        """
        Return ``True`` if *now* is past the stored ``next_allowed_ts``
        **or** if the key is unseen (implicitly ready).
        """
        with self._lock:
            ts, _ = self._state.get(key, (0.0, 0))
            return time.time() >= ts

    def on_error(self, key: Key, err_code: int) -> None:
        """
        Record a retry-worthy error for *key* and advance exponential back-off.

        Non-retry codes are ignored so callers can still invoke ``ready()`` freely.
        """
        if err_code not in SHOULD_RETRY:
            return

        with self._lock:
            _, attempt = self._state.get(key, (0.0, 0))

            # Exponential delay calculation
            if attempt >= self.max_attempts:
                delay = self.max_delay
            else:
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)

            self._state[key] = (time.time() + delay, attempt + 1)

    # ---------------------------------------------------------------------
    # Success = clear state
    # ---------------------------------------------------------------------
    def on_success(self, key: Key) -> bool:
        """
        Clear retry/back-off state for *key*.

        Returns ``True`` iff there *was* a pending back-off entry that we removed.
        """
        with self._lock:
            existed = key in self._state
            if existed:
                del self._state[key]
            return existed

    # Backwards-compat alias (older code called .reset_on_success)
    reset_on_success = on_success

    # ───────────────────────────────────────────────────────────
    # Debug helpers (optional)
    # ───────────────────────────────────────────────────────────
    def _dump(self) -> Dict[Key, Tuple[float, int]]:
        """Return a *copy* of internal state (for testing / debug)."""
        with self._lock:
            return dict(self._state)
