"""List pagination helpers for API responses."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy.orm import Query

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def clamp_page(page: int | None) -> int:
    try:
        p = int(page) if page is not None else DEFAULT_PAGE
    except (TypeError, ValueError):
        p = DEFAULT_PAGE
    return max(1, p)


def clamp_page_size(page_size: int | None) -> int:
    try:
        s = int(page_size) if page_size is not None else DEFAULT_PAGE_SIZE
    except (TypeError, ValueError):
        s = DEFAULT_PAGE_SIZE
    return max(1, min(s, MAX_PAGE_SIZE))


def paginate_query(query: Query, *, page: int, page_size: int) -> tuple[list[Any], int]:
    """
    Run COUNT + LIMIT/OFFSET on an already-filtered SQLAlchemy query.
    Caller should apply order_by before paginate for stable pages.
    """
    total = query.order_by(None).count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    return items, total


def page_payload(items: list[Any], *, total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
