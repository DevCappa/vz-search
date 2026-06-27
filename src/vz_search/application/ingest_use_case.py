from __future__ import annotations

from vz_search.domain.entities import IngestStats
from vz_search.domain.ports.cache_port import CachePort
from vz_search.domain.ports.ingest_port import IngestPort


class IngestUseCase:
    def __init__(self, ingestor: IngestPort, cache: CachePort) -> None:
        self._ingestor = ingestor
        self._cache = cache

    def execute(self, *, full_rebuild: bool = False) -> IngestStats:
        stats = self._ingestor.ingest(full_rebuild=full_rebuild)
        self._cache.clear()
        return stats
