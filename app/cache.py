"""In-memory LRU + TTL cache (SPEC.md section 7). Stateless service, cache-miss always OK."""

from __future__ import annotations

from typing import Any

from cachetools import TTLCache


class Cache:
    """Thin wrapper over cachetools.TTLCache. Disabled when ttl<=0 or max_entries<=0."""

    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        self.enabled = ttl_seconds > 0 and max_entries > 0
        self._cache: TTLCache | None = (
            TTLCache(maxsize=max_entries, ttl=ttl_seconds) if self.enabled else None
        )

    def get(self, key: str) -> Any | None:
        if self._cache is None:
            return None
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        if self._cache is None:
            return
        self._cache[key] = value

    def clear(self) -> None:
        if self._cache is not None:
            self._cache.clear()
