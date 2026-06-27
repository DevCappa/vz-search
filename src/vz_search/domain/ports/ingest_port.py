from __future__ import annotations

from typing import Protocol

from vz_search.domain.entities import IngestStats


class IngestPort(Protocol):
    def ingest(self, *, full_rebuild: bool = False) -> IngestStats:
        ...
