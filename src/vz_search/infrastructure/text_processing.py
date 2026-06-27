from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from rapidfuzz import fuzz, process

from vz_search.domain.entities import PersonRecord, SearchQuery

STATE_NAMES = {
    "amazonas",
    "anzoategui",
    "anzoátegui",
    "apure",
    "aragua",
    "barinas",
    "bolivar",
    "bolívar",
    "carabobo",
    "cojedes",
    "delta amacuro",
    "distrito capital",
    "falcon",
    "falcón",
    "guarico",
    "guárico",
    "la guaira",
    "lara",
    "merida",
    "mérida",
    "miranda",
    "monagas",
    "nueva esparta",
    "portuguesa",
    "sucre",
    "tachira",
    "táchira",
    "trujillo",
    "yaracuy",
    "zulia",
    "caracas",
}


def detect_state(text: str) -> str | None:
    lower = text.lower()
    for state in STATE_NAMES:
        if state in lower:
            return state.title()
    return None


def guess_hospital_from_path(path: Path, data_dir: Path) -> str:
    parent = path.parent.name.replace("_", " ").replace("-", " ")
    if path.parent != data_dir and path.parent.name.lower() != "data":
        return parent
    return path.stem.replace("_", " ").replace("-", " ")


def split_into_records(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    records: list[str] = []
    buffer: list[str] = []

    for line in lines:
        looks_like_name = bool(
            re.match(
                r"^[A-ZÁÉÍÓÚÑa-záéíóúñ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ][a-záéíóúñ]+)+",
                line,
            )
        )
        if looks_like_name and buffer:
            records.append(" | ".join(buffer))
            buffer = [line]
        else:
            buffer.append(line)

    if buffer:
        records.append(" | ".join(buffer))

    if len(records) <= 1 and len(text) > 100:
        chunks = re.split(r"\n{2,}", text)
        records = [c.strip() for c in chunks if len(c.strip()) > 15]

    return records if records else [text.strip()] if text.strip() else []


def build_fts_query(name: str) -> str | None:
    terms = [t for t in name.strip().split() if len(t) >= 2]
    if not terms:
        return None
    sanitized = []
    for term in terms:
        clean = re.sub(r"[^\wáéíóúñÁÉÍÓÚÑ]", "", term, flags=re.UNICODE)
        if clean:
            sanitized.append(f'"{clean}"')
    if not sanitized:
        return None
    return " AND ".join(sanitized)


def rank_by_name(records: list[PersonRecord], name: str, limit: int) -> list[PersonRecord]:
    if not name.strip() or not records:
        return records[:limit]

    choices = {record.id: record.content for record in records}
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
                score=int(score),
            )
        )

    return ranked
