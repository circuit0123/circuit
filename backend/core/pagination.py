"""One pagination style everywhere: limit/offset in, {items, count, next} out."""

from typing import Generic, TypeVar

from ninja import Query, Schema
from pydantic import Field

T = TypeVar("T")
MAX_LIMIT = 100


class PageParams(Schema):
    limit: int = Field(20, ge=1, le=MAX_LIMIT)
    offset: int = Field(0, ge=0)


class Page(Schema, Generic[T]):
    items: list[T]
    count: int
    next_offset: int | None = None


def paginate(queryset_or_list, params: PageParams, serialize=lambda x: x) -> dict:
    if hasattr(queryset_or_list, "count") and callable(queryset_or_list.count) and not isinstance(queryset_or_list, list):
        total = queryset_or_list.count()
    else:
        total = len(queryset_or_list)
    window = queryset_or_list[params.offset : params.offset + params.limit]
    nxt = params.offset + params.limit
    return {
        "items": [serialize(x) for x in window],
        "count": total,
        "next_offset": nxt if nxt < total else None,
    }


__all__ = ["Page", "PageParams", "Query", "paginate"]
