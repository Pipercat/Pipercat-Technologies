"""Rate limiting for authentication attempts (S1V2-02-008)."""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, *, now: float | None = None) -> bool:
        current = now if now is not None else time.monotonic()
        attempts = self._attempts[key]
        cutoff = current - self._window_seconds
        while attempts and attempts[0] < cutoff:
            attempts.pop(0)
        if len(attempts) >= self._max_attempts:
            return False
        attempts.append(current)
        return True

    def reset(self, key: str) -> None:
        """Called after a *successful* login so a legitimate user isn't
        penalized by earlier failed attempts once they get it right."""
        self._attempts.pop(key, None)
