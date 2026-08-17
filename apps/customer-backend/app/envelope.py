"""SystemONE API v1 response envelope (S1V2-01-004).

Every response — success or error — uses this shape. See
docs/architecture/api-contract.md for the full contract.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiError(BaseModel):
    code: str
    message: str
    correlationId: str
    details: dict | None = None


class Envelope(BaseModel, Generic[DataT]):
    success: bool
    data: DataT | None = None
    error: ApiError | None = None


def ok(data: DataT) -> Envelope[DataT]:
    return Envelope[DataT](success=True, data=data, error=None)
