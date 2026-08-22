"""Idempotency-Key support for critical write operations (S1V2-01-004).

In-memory store only — sufficient to define and test the contract now.
Must move to a persistent store (alongside PostgreSQL, S1V2-02-001) before
this is relied on across process restarts in production; tracked as a known
limitation rather than silently assumed.
"""

from typing import Any


class IdempotencyStore:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, response: Any) -> None:
        self._store[key] = response


idempotency_store = IdempotencyStore()
