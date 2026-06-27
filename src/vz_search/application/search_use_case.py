from __future__ import annotations

import hashlib
import json

from vz_search.domain.entities import SearchQuery, SearchResult
from vz_search.domain.ports.cache_port import CachePort
from vz_search.domain.ports.record_repository import RecordRepository

CACHE_PREFIX = "search:"


class SearchUseCase:
    def __init__(self, repository: RecordRepository, cache: CachePort) -> None:
        self._repository = repository
        self._cache = cache

    def execute(self, query: SearchQuery) -> SearchResult:
        if query.is_empty():
            return SearchResult(query=query, records=(), cached=False)

        cache_key = self._cache_key(query)
        cached_payload = self._cache.get(cache_key)
        if cached_payload is not None:
            return SearchResult(
                query=query,
                records=tuple(cached_payload),
                cached=True,
            )

        records = self._repository.search(query)
        self._cache.set(cache_key, records)
        return SearchResult(query=query, records=tuple(records), cached=False)

    @staticmethod
    def _cache_key(query: SearchQuery) -> str:
        payload = json.dumps(
            {
                "name": query.name.strip().lower(),
                "hospital": query.hospital.strip().lower(),
                "state": query.state.strip().lower(),
                "limit": query.limit,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return f"{CACHE_PREFIX}{digest}"
