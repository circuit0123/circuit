"""One pagination style everywhere: limit/offset in, {items, count, next} out."""

import base64
import json
from typing import Generic, TypeVar

from ninja import Query, Schema
from pydantic import Field

from core.errors import ApiError

T = TypeVar("T")
MAX_LIMIT = 100


class PageParams(Schema):
    limit: int = Field(20, ge=1, le=MAX_LIMIT)
    offset: int = Field(0, ge=0)


class Page(Schema, Generic[T]):
    items: list[T]
    count: int
    next_offset: int | None = None


class CursorParams(Schema):
    """Live feeds (Pulse, messages) use a cursor, not offsets: new items arriving must not shift the next page."""

    cursor: str | None = None
    limit: int = Field(20, ge=1, le=MAX_LIMIT)


def encode_cursor(*parts) -> str:
    return base64.urlsafe_b64encode(json.dumps(parts).encode()).decode().rstrip("=")


def decode_cursor(raw: str, size: int) -> list:
    try:
        parts = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if isinstance(parts, list) and len(parts) == size:
            return parts
    except ValueError:
        pass
    raise ApiError(422, "bad_cursor", "That page marker is not valid. Reload from the top.")


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


__all__ = ["CursorParams", "Page", "PageParams", "Query", "decode_cursor", "encode_cursor", "paginate"]
