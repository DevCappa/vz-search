from __future__ import annotations

import threading

from rapidfuzz import fuzz, process

from vz_search.domain.entities import ExtractedPerson, PersonRecord, SearchQuery


class InMemoryRecordRepository:
    """Almacén volátil en RAM. Se pierde al reiniciar el proceso."""

    def __init__(self) -> None:
        self._records: list[PersonRecord] = []
        self._lock = threading.RLock()
        self._next_id = 1

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._next_id = 1

    def load_snapshot(self, records: list[PersonRecord]) -> None:
        with self._lock:
            self._records = list(records)
            self._next_id = max((record.id for record in records), default=0) + 1

    def all_records(self) -> list[PersonRecord]:
        with self._lock:
            return list(self._records)

    def add_many(self, records: list[PersonRecord]) -> None:
        with self._lock:
            self._records.extend(records)

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def search(self, query: SearchQuery) -> list[PersonRecord]:
        with self._lock:
            candidates = list(self._records)

        filtered: list[PersonRecord] = []
        name_q = query.name.strip().lower()
        hospital_q = query.hospital.strip().lower()
        state_q = query.state.strip().lower()

        for record in candidates:
            haystack = " ".join(
                filter(
                    None,
                    [
                        record.full_name,
                        record.content,
                        record.hospital,
                        record.state,
                        record.cedula,
                        record.source_file,
                    ],
                )
            ).lower()

            if name_q:
                terms = name_q.split()
                if not all(term in haystack for term in terms):
                    continue
            if hospital_q and hospital_q not in (record.hospital or "").lower() and hospital_q not in haystack:
                continue
            if state_q and state_q not in (record.state or "").lower() and state_q not in haystack:
                continue
            filtered.append(record)

        if query.name.strip() and filtered:
            return self._rank(filtered, query.name, query.limit)

        return filtered[: query.limit]

    @staticmethod
    def _rank(records: list[PersonRecord], name: str, limit: int) -> list[PersonRecord]:
        choices = {
            record.id: record.full_name or record.content for record in records
        }
        matches = process.extract(name, choices, scorer=fuzz.partial_ratio, limit=limit)
        ranked: list[PersonRecord] = []
        seen: set[int] = set()

        for _, score, record_id in matches:
            if record_id in seen:
                continue
            seen.add(record_id)
            source = next(record for record in records if record.id == record_id)
            ranked.append(
                PersonRecord(
                    id=source.id,
                    source_file=source.source_file,
                    hospital=source.hospital,
                    state=source.state,
                    content=source.content,
                    full_name=source.full_name,
                    cedula=source.cedula,
                    score=int(score),
                )
            )
        return ranked

    def create_records(
        self,
        source_file: str,
        extracted: list[ExtractedPerson],
        default_hospital: str | None,
        default_state: str | None,
    ) -> list[PersonRecord]:
        created: list[PersonRecord] = []
        with self._lock:
            for person in extracted:
                record = PersonRecord(
                    id=self._next_id,
                    source_file=source_file,
                    hospital=person.hospital or default_hospital,
                    state=person.state or default_state,
                    content=person.to_content(),
                    full_name=person.full_name,
                    cedula=person.cedula,
                )
                self._next_id += 1
                created.append(record)
                self._records.append(record)
        return created
