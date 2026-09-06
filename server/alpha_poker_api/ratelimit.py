from __future__ import annotations

import time
import threading
from collections import defaultdict


class RateLimiter:
    """Conservative in-process fixed-window limiter for a single instance.

    State lives in a plain dict, not a shared store, so this only makes sense
    for the single-container Lightsail deployment this app runs behind. A
    multi-instance deployment would need a shared backend (e.g. Redis)
    instead of this class.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.pop(0)
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True
