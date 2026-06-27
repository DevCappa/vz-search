from __future__ import annotations

import sqlite3
from pathlib import Path

import fitz

from vz_search.domain.entities import IngestStats
from vz_search.infrastructure.text_processing import (
    detect_state,
    guess_hospital_from_path,
    split_into_records,
)


def extract_text_from_pdf(path: Path) -> str:
    doc = fitz.open(path)
    parts: list[str] = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts)


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(path)
    if suffix in {".txt", ".csv", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    return ""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            hospital TEXT,
            state TEXT,
            content TEXT NOT NULL,
            content_lower TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
            content,
            hospital,
            state,
            source_file,
            content='records',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN
            INSERT INTO records_fts(rowid, content, hospital, state, source_file)
            VALUES (new.id, new.content, new.hospital, new.state, new.source_file);
        END;

        CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN
            INSERT INTO records_fts(records_fts, rowid, content, hospital, state, source_file)
            VALUES ('delete', old.id, old.content, old.hospital, old.state, old.source_file);
        END;
        """
    )


class FileIngestor:
    def __init__(self, data_dir: Path, db_path: Path) -> None:
        self._data_dir = data_dir
        self._db_path = db_path

    def ingest(self) -> IngestStats:
        self._data_dir.mkdir(exist_ok=True)

        if self._db_path.exists():
            self._db_path.unlink()

        conn = sqlite3.connect(self._db_path)
        init_db(conn)

        files_processed = 0
        records_created = 0
        errors: list[str] = []

        patterns = ("**/*.pdf", "**/*.txt", "**/*.csv", "**/*.md")
        files: list[Path] = []
        for pattern in patterns:
            files.extend(self._data_dir.glob(pattern))

        for path in sorted(set(files)):
            try:
                text = extract_text_from_file(path)
                if not text.strip():
                    continue

                hospital = guess_hospital_from_path(path, self._data_dir)
                rel = str(path.relative_to(self._data_dir))
                chunks = split_into_records(text)

                for chunk in chunks:
                    state = detect_state(chunk) or detect_state(hospital) or detect_state(rel)
                    conn.execute(
                        """
                        INSERT INTO records (source_file, hospital, state, content, content_lower)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (rel, hospital, state, chunk, chunk.lower()),
                    )
                    records_created += 1

                files_processed += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: {exc}")

        conn.commit()
        conn.close()

        return IngestStats(files=files_processed, records=records_created, errors=tuple(errors))
