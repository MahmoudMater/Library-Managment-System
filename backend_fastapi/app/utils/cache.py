from __future__ import annotations

import json
from typing import Any, Callable, TypeVar

from redis import Redis

T = TypeVar("T")

# Books cache-aside keys (shared with routers)
BOOKS_LIST_KEY = "books:list"


def book_cache_key(book_id: int) -> str:
    return f"books:id:{book_id}"


def borrow_user_history_key(user_id: int) -> str:
    return f"borrow:user:{user_id}"


def invalidate_books_cache(redis_client: Redis, *, book_id: int | None) -> None:
    keys = [BOOKS_LIST_KEY]
    if book_id is not None:
        keys.append(book_cache_key(book_id))
    cache_delete(redis_client, *keys)


def invalidate_borrow_user_cache(redis_client: Redis, user_id: int) -> None:
    cache_delete(redis_client, borrow_user_history_key(user_id))


def cache_delete_pattern(redis_client: Redis, pattern: str) -> int:
    """Delete all keys matching pattern (SCAN + DEL). Use sparingly on large DBs."""
    deleted = 0
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            deleted += int(redis_client.delete(*keys))
        if cursor == 0:
            break
    return deleted


def cache_get(redis_client: Redis, key: str) -> Any | None:
    raw = redis_client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def cache_set(redis_client: Redis, key: str, value: Any, *, ttl_seconds: int | None = 60) -> bool:
    raw = json.dumps(value, default=str)
    if ttl_seconds is None:
        return bool(redis_client.set(key, raw))
    return bool(redis_client.setex(key, ttl_seconds, raw))


def cache_delete(redis_client: Redis, *keys: str) -> int:
    if not keys:
        return 0
    return int(redis_client.delete(*keys))


def cache_or_compute(
    redis_client: Redis,
    key: str,
    compute: Callable[[], T],
    *,
    ttl_seconds: int | None = 60,
) -> T:
    cached = cache_get(redis_client, key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = compute()
    cache_set(redis_client, key, value, ttl_seconds=ttl_seconds)
    return value
