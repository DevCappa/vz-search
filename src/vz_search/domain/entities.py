from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersonRecord:
    id: int
    source_file: str
    hospital: str | None
    state: str | None
    content: str
    full_name: str | None = None
    cedula: str | None = None
    score: int | None = None


@dataclass(frozen=True, slots=True)
class SearchQuery:
    name: str = ""
    hospital: str = ""
    state: str = ""
    limit: int = 50

    def is_empty(self) -> bool:
        return not (self.name.strip() or self.hospital.strip() or self.state.strip())


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: SearchQuery
    records: tuple[PersonRecord, ...]
    cached: bool = False

    @property
    def total(self) -> int:
        return len(self.records)


@dataclass(frozen=True, slots=True)
class IngestStats:
    files: int
    records: int
    errors: tuple[str, ...]
    ai_calls: int = 0
    skipped: int = 0
    pending: int = 0


@dataclass(frozen=True, slots=True)
class ExtractedPerson:
    full_name: str
    hospital: str | None = None
    state: str | None = None
    cedula: str | None = None
    age: str | None = None
    condition: str | None = None
    notes: str | None = None

    def to_content(self) -> str:
        parts = [self.full_name]
        if self.cedula:
            parts.append(f"Cédula: {self.cedula}")
        if self.age:
            parts.append(f"Edad: {self.age}")
        if self.condition:
            parts.append(f"Condición: {self.condition}")
        if self.notes:
            parts.append(f"Notas: {self.notes}")
        return " | ".join(parts)
