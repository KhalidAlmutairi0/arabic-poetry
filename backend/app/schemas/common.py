from pydantic import BaseModel
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], total: int, page: int, limit: int):
        return cls(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit if limit > 0 else 0,
        )


class HealthResponse(BaseModel):
    status: str
    database: bool
    redis: bool
    meilisearch: bool
    version: str
