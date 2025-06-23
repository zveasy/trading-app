#!/usr/bin/env python3
"""
RetryRegistry
─────────────
Keyed exponential back-off with auto-reset.

Rules
-----
1. An entry keeps two numbers:
     • attempts  – how many errors we’ve seen
     • next_ok   – timestamp when processing is allowed again
2. For *retry-worthy* error codes (in SHOULD_RETRY) we block as soon as
   attempts ≥ max_attempts.
3. For all other errors we block only when attempts > max_attempts.
4. on_success(key) wipes the entry entirely.
"""

from __future__ import annotations
import threading, time
from typing import Dict, Tuple

# IB codes worth retrying (extend when needed)
SHOULD_RETRY: set[int] = {1100, 1101, 200, 202, 104}

Key = Tuple[int, str]           # (proto_id, symbol)


class _Entry:                    # internal state
    __slots__ = ("attempts", "next_ok")
    def __init__(self) -> None:
        self.attempts = 0
        self.next_ok  = 0.0


class RetryRegistry:
    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_delay   = base_delay
        self.max_delay    = max_delay
        self._state: Dict[Key, _Entry] = {}
        self._lock = threading.Lock()

    # ───────────────────────────── helpers ─────────────────────────────
    def ready(self, key: Key) -> bool:
        """True if *now* ≥ next_ok or key unseen."""
        with self._lock:
            entry = self._state.get(key)
            return True if entry is None else time.time() >= entry.next_ok

    def _calc_delay(self, attempts_over: int) -> float:
        """Exponential back-off but never beyond max_delay."""
        return min(self.base_delay * (2 ** attempts_over), self.max_delay)

    def on_error(self, key: Key, err_code: int) -> None:
        """Register an error and (maybe) start / extend back-off."""
        with self._lock:
            entry = self._state.setdefault(key, _Entry())
            entry.attempts += 1

            # decide when to start blocking
            if (
                (err_code in SHOULD_RETRY and entry.attempts >= self.max_attempts)
                or (err_code not in SHOULD_RETRY and entry.attempts > self.max_attempts)
            ):
                over = entry.attempts - self.max_attempts
                entry.next_ok = time.time() + self._calc_delay(max(0, over))
            else:
                # still inside grace window
                entry.next_ok = 0.0

    def on_success(self, key: Key) -> bool:
        """Clear state; return True if an entry existed."""
        with self._lock:
            return self._state.pop(key, None) is not None

    # backwards-compat alias
    reset_on_success = on_success

    # debugging hook
    def _dump(self):
        with self._lock:
            return {k: (v.attempts, v.next_ok) for k, v in self._state.items()}
