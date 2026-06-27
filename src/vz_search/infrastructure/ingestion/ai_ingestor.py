from __future__ import annotations

import time
from pathlib import Path

from vz_search.domain.entities import IngestStats
from vz_search.domain.ports.document_analyzer import DocumentAnalyzerPort
from vz_search.infrastructure.persistence.sqlite_person_index import SqlitePersonIndex
from vz_search.infrastructure.text_processing import detect_state, guess_hospital_from_path

SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".txt", ".csv", ".md"}


def count_data_files(data_dir: Path) -> int:
    if not data_dir.exists():
        return 0
    return sum(
        1
        for path in data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


class AiIngestor:
    """
    Ingestión IA con persistencia SQLite.
    - Checkpoint por archivo (no se pierde progreso)
    - Incremental: solo archivos nuevos o fallidos
    - Pausa entre llamadas para cuota gratis
    """

    def __init__(
        self,
        data_dir: Path,
        index: SqlitePersonIndex,
        analyzer: DocumentAnalyzerPort,
        request_delay_seconds: float = 7.0,
        incremental: bool = True,
    ) -> None:
        self._data_dir = data_dir
        self._index = index
        self._analyzer = analyzer
        self._request_delay_seconds = request_delay_seconds
        self._incremental = incremental

    def ingest(self, *, full_rebuild: bool = False) -> IngestStats:
        self._data_dir.mkdir(exist_ok=True)

        if full_rebuild or not self._incremental:
            self._index.clear()

        processed_ok = self._index.get_ok_files() if self._incremental and not full_rebuild else set()

        files_processed = 0
        records_added = 0
        ai_calls = 0
        skipped = 0
        errors: list[str] = []

        all_files = self._discover_files()
        if not all_files:
            return IngestStats(
                files=0,
                records=self._index.count(),
                errors=(
                    f"No hay archivos en '{self._data_dir}'. "
                    "En Railway la carpeta data/ está vacía: indexa en tu PC y sube search.db "
                    "(VZ_SEARCH_DB_BOOTSTRAP_URL) o incluye los PDFs en el deploy.",
                ),
                ai_calls=0,
                skipped=0,
                pending=0,
            )
        pending = [
            path
            for path in all_files
            if full_rebuild
            or not self._incremental
            or str(path.relative_to(self._data_dir)) not in processed_ok
        ]

        for index, path in enumerate(pending):
            rel = str(path.relative_to(self._data_dir))

            if self._incremental and not full_rebuild and rel in processed_ok:
                skipped += 1
                continue

            if index > 0 and self._request_delay_seconds > 0:
                time.sleep(self._request_delay_seconds)

            hospital_hint = guess_hospital_from_path(path, self._data_dir)
            state_hint = detect_state(hospital_hint) or detect_state(rel)

            persons, error = self._analyzer.analyze_file(
                path=path,
                source_hint=rel,
                hospital_hint=hospital_hint,
            )
            ai_calls += 1

            if error:
                self._index.mark_file_failed(rel, error)
                errors.append(f"{rel}: {error}")
                continue

            if not persons:
                msg = "IA no encontró personas en el documento"
                self._index.mark_file_failed(rel, msg)
                errors.append(f"{rel}: {msg}")
                continue

            added = self._index.replace_file_records(
                source_file=rel,
                extracted=persons,
                default_hospital=hospital_hint,
                default_state=state_hint,
            )
            records_added += added
            files_processed += 1

        return IngestStats(
            files=files_processed,
            records=self._index.count(),
            errors=tuple(errors),
            ai_calls=ai_calls,
            skipped=skipped,
            pending=len(pending),
        )

    def _discover_files(self) -> list[Path]:
        return [
            path
            for path in sorted(self._data_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ]
