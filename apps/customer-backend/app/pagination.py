"""Cursor-based pagination convention (S1V2-01-004).

Offset pagination is intentionally avoided: it is not stable under
concurrent writes, which matters once events/audit entries are written
continuously. Cursor is an opaque string (currently the index as text) —
callers must not parse it.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    nextCursor: str | None = None


def paginate(items: list[ItemT], limit: int, cursor: str | None) -> Page[ItemT]:
    start = int(cursor) if cursor else 0
    window = items[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(items) else None
    return Page[ItemT](items=window, nextCursor=next_cursor)
