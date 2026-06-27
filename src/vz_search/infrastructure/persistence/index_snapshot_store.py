from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from vz_search.domain.entities import ExtractedPerson, PersonRecord


class IndexSnapshotStore:
    """Guarda el índice en disco para no perder progreso ni repetir IA."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def save(
        self,
        records: list[PersonRecord],
        processed_files: set[str],
        failed_files: dict[str, str],
    ) -> None:
        payload = {
            "processed_files": sorted(processed_files),
            "failed_files": failed_files,
            "records": [asdict(record) for record in records],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> tuple[list[PersonRecord], set[str], dict[str, str]]:
        if not self._path.exists():
            return [], set(), {}

        payload = json.loads(self._path.read_text(encoding="utf-8"))
        records = [
            PersonRecord(
                id=item["id"],
                source_file=item["source_file"],
                hospital=item.get("hospital"),
                state=item.get("state"),
                content=item["content"],
                full_name=item.get("full_name"),
                cedula=item.get("cedula"),
                score=item.get("score"),
            )
            for item in payload.get("records", [])
        ]
        processed = set(payload.get("processed_files", []))
        failed = dict(payload.get("failed_files", {}))
        return records, processed, failed

    def exists(self) -> bool:
        return self._path.exists()
