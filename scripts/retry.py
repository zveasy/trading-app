import time
from collections import defaultdict
from typing import Dict, Tuple, Optional

# IB codes that warrant retry (extend as needed)
SHOULD_RETRY = {103, 354, 399, 202}

class RetryState:
    __slots__ = ("attempts_left", "next_ts")
    def __init__(self, attempts_left: int, next_ts: float):
        self.attempts_left = attempts_left
        self.next_ts      = next_ts

class RetryRegistry:
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay   = base_delay
        self._store: Dict[Tuple[int,str], RetryState] = defaultdict(
            lambda: RetryState(max_attempts, 0.0)
        )

    # ------------------------------------------------------------------ #
    def on_error(self, proto_key: Tuple[int,str], code: int) -> Optional[float]:
        """Register failed attempt, return delay (seconds) or None if give-up."""
        st = self._store[proto_key]
        if st.attempts_left <= 0:
            return None
        backoff  = self.base_delay * (2 ** (self.max_attempts - st.attempts_left))
        st.attempts_left -= 1
        st.next_ts = time.time() + backoff
        return backoff

    def ready(self, proto_key: Tuple[int,str]) -> bool:
        """True when we can re-attempt."""
        st = self._store[proto_key]
        return time.time() >= st.next_ts
