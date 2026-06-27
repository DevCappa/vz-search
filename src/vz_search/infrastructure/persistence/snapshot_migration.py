from __future__ import annotations

from pathlib import Path

from vz_search.domain.entities import ExtractedPerson
from vz_search.infrastructure.persistence.index_snapshot_store import IndexSnapshotStore
from vz_search.infrastructure.persistence.sqlite_person_index import SqlitePersonIndex


def migrate_snapshot_to_sqlite(snapshot_path: Path, index: SqlitePersonIndex) -> int:
    """Importa index_snapshot.json previo a SQLite si la BD está vacía."""
    if index.count() > 0 or not snapshot_path.exists():
        return 0

    store = IndexSnapshotStore(snapshot_path)
    records, processed_files, failed_files = store.load()
    if not records:
        return 0

    by_file: dict[str, list[ExtractedPerson]] = {}
    for record in records:
        by_file.setdefault(record.source_file, []).append(
            ExtractedPerson(
                full_name=record.full_name or record.content.split("|")[0].strip(),
                hospital=record.hospital,
                state=record.state,
                cedula=record.cedula,
                notes=record.content,
            )
        )

    imported = 0
    for source_file, persons in by_file.items():
        index.replace_file_records(source_file, persons, None, None)
        imported += len(persons)

    for source_file in processed_files:
        if source_file not in by_file:
            index.mark_file_failed(source_file, "Migrado sin registros")

    for source_file, error in failed_files.items():
        if source_file not in processed_files:
            index.mark_file_failed(source_file, error)

    return imported
