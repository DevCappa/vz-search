from __future__ import annotations

from typing import Protocol

from vz_search.domain.entities import ExtractedPerson, PersonRecord, SearchQuery


class RecordRepository(Protocol):
    def search(self, query: SearchQuery) -> list[PersonRecord]:
        ...

    def count(self) -> int:
        ...

    def clear(self) -> None:
        ...

    def add_many(self, records: list[PersonRecord]) -> None:
        ...
