from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from scripts.metrics_server import throttle_blocked_total


class ThrottleException(Exception):
    pass


@dataclass
class ContractSpec:
    symbol: str


class Throttle:
    def __init__(
        self, max_orders_per_sec: int = 20, max_notional: float = 2_000_000
    ) -> None:
        self.max_orders_per_sec = max_orders_per_sec
        self.max_notional = max_notional
        self._lock = threading.Lock()
        self._window_start = 0.0
        self._count = 0
        self._notional = 0.0

    def _reset_window(self, now: float) -> None:
        self._window_start = now
        self._count = 0
        self._notional = 0.0

    def block_if_needed(
        self, contract: ContractSpec, quantity: int, price: float
    ) -> None:
        """Raise ThrottleException if the new order would exceed limits."""
        now = time.time()
        with self._lock:
            if now - self._window_start >= 1.0:
                self._reset_window(now)

            est_count = self._count + 1
            est_notional = self._notional + abs(quantity) * price
            if est_count > self.max_orders_per_sec or est_notional > self.max_notional:
                throttle_blocked_total.inc()
                raise ThrottleException(
                    f"Throttle exceeded for {contract.symbol}: qty={quantity} price={price}"
                )

            self._count = est_count
            self._notional = est_notional
