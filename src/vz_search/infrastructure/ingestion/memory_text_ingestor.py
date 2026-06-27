from __future__ import annotations

from pathlib import Path

from vz_search.domain.entities import ExtractedPerson, IngestStats
from vz_search.infrastructure.ingestion.file_ingestor import extract_text_from_file
from vz_search.infrastructure.persistence.in_memory_record_repository import InMemoryRecordRepository
from vz_search.infrastructure.text_processing import detect_state, guess_hospital_from_path, split_into_records

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".csv", ".md"}


class MemoryTextIngestor:
    """Fallback sin IA: solo PDFs con texto seleccionable."""

    def __init__(self, data_dir: Path, repository: InMemoryRecordRepository) -> None:
        self._data_dir = data_dir
        self._repository = repository

    def ingest(self, *, full_rebuild: bool = False) -> IngestStats:
        self._data_dir.mkdir(exist_ok=True)
        self._repository.clear()

        files_processed = 0
        records_created = 0
        errors: list[str] = []

        for path in sorted(self._data_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue

            try:
                text = extract_text_from_file(path)
                if not text.strip():
                    errors.append(f"{path.name}: sin texto (probablemente escaneado — usa modo IA)")
                    continue

                rel = str(path.relative_to(self._data_dir))
                hospital = guess_hospital_from_path(path, self._data_dir)
                state = detect_state(hospital) or detect_state(rel)
                chunks = split_into_records(text)

                extracted = [
                    ExtractedPerson(
                        full_name=chunk.split("|")[0].strip()[:120],
                        hospital=hospital,
                        state=state,
                        notes=chunk,
                    )
                    for chunk in chunks
                ]
                batch = self._repository.create_records(rel, extracted, hospital, state)
                records_created += len(batch)
                files_processed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: {exc}")

        return IngestStats(files=files_processed, records=records_created, errors=tuple(errors), ai_calls=0)
