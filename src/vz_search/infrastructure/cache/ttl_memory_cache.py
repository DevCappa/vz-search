from __future__ import annotations

from cachetools import TTLCache

from vz_search.domain.entities import PersonRecord


class TtlMemoryCache:
    def __init__(self, maxsize: int, ttl: int) -> None:
        self._store: TTLCache[str, list[PersonRecord]] = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> list[PersonRecord] | None:
        return self._store.get(key)

    def set(self, key: str, value: list[PersonRecord]) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
