from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from fastapi.responses import JSONResponse


def api_response(
    *,
    data: Any = None,
    message: str | None = None,
    status_code: int = 200,
    error: Any = None,
    meta: Mapping[str, Any] | None = None,
) -> JSONResponse:
    """
    Standard response shape across the API (matches Flask `app/utils/response.py`).
    """
    payload: dict[str, Any] = {
        "success": 200 <= status_code < 400,
        "message": message,
        "data": data,
        "error": error,
        "meta": dict(meta) if meta else None,
    }
    return JSONResponse(content=payload, status_code=status_code)


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int
    total: int

    @property
    def pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


def paginated_response(
    *,
    items: Sequence[Any],
    pagination: Pagination,
    message: str | None = None,
    status_code: int = 200,
    meta: Mapping[str, Any] | None = None,
) -> JSONResponse:
    base_meta: dict[str, Any] = {
        "pagination": {
            **asdict(pagination),
            "pages": pagination.pages,
        }
    }
    if meta:
        base_meta.update(dict(meta))

    return api_response(
        data={"items": list(items)},
        message=message,
        status_code=status_code,
        meta=base_meta,
    )
