from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from vz_search.domain.entities import ExtractedPerson, PersonRecord, SearchQuery
from vz_search.infrastructure.text_processing import build_fts_query, rank_by_name


def normalize_source_file(source_file: str) -> str:
    return source_file.replace("\\", "/").lstrip("/")

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    hospital TEXT,
    state TEXT,
    full_name TEXT,
    cedula TEXT,
    content TEXT NOT NULL,
    content_lower TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_files (
    source_file TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    processed_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    content,
    full_name,
    hospital,
    state,
    cedula,
    source_file,
    content='records',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN
    INSERT INTO records_fts(rowid, content, full_name, hospital, state, cedula, source_file)
    VALUES (new.id, new.content, new.full_name, new.hospital, new.state, new.cedula, new.source_file);
END;

CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, content, full_name, hospital, state, cedula, source_file)
    VALUES ('delete', old.id, old.content, old.full_name, old.hospital, old.state, old.cedula, old.source_file);
END;

CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, content, full_name, hospital, state, cedula, source_file)
    VALUES ('delete', old.id, old.content, old.full_name, old.hospital, old.state, old.cedula, old.source_file);
    INSERT INTO records_fts(rowid, content, full_name, hospital, state, cedula, source_file)
    VALUES (new.id, new.content, new.full_name, new.hospital, new.state, new.cedula, new.source_file);
END;
"""


class SqlitePersonIndex:
    """Fuente de verdad en disco. Checkpoint por archivo + respaldo automático."""

    def __init__(self, db_path: Path, backup_dir: Path, backup_keep: int = 5) -> None:
        self._db_path = db_path
        self._backup_dir = backup_dir
        self._backup_keep = backup_keep
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM records")
            conn.execute("DELETE FROM ingest_files")

    def add_many(self, records: list[PersonRecord]) -> None:
        raise NotImplementedError("Usa replace_file_records para ingestión")

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM records").fetchone()
            return int(row["total"]) if row else 0

    def search(self, query: SearchQuery) -> list[PersonRecord]:
        fts_query = build_fts_query(query.name)
        clauses: list[str] = []
        params: list[str | int] = []

        if fts_query:
            clauses.append("id IN (SELECT rowid FROM records_fts WHERE records_fts MATCH ?)")
            params.append(fts_query)
        elif query.name.strip():
            for term in query.name.strip().split():
                clauses.append("content_lower LIKE ?")
                params.append(f"%{term.lower()}%")

        if query.hospital.strip():
            clauses.append("hospital LIKE ?")
            params.append(f"%{query.hospital.strip()}%")

        if query.state.strip():
            clauses.append("(state LIKE ? OR content_lower LIKE ?)")
            params.extend([f"%{query.state.strip()}%", f"%{query.state.strip().lower()}%"])

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"""
            SELECT id, source_file, hospital, state, full_name, cedula, content
            FROM records
            WHERE {where}
            ORDER BY id
            LIMIT ?
        """
        params.append(min(query.limit * 10, 500))

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        records = [
            PersonRecord(
                id=row["id"],
                source_file=row["source_file"],
                hospital=row["hospital"],
                state=row["state"],
                full_name=row["full_name"],
                cedula=row["cedula"],
                content=row["content"],
            )
            for row in rows
        ]
        return rank_by_name(records, query.name, query.limit)

    def get_ok_files(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT source_file FROM ingest_files WHERE status = 'ok'"
            ).fetchall()
        return {row["source_file"] for row in rows}

    def replace_file_records(
        self,
        source_file: str,
        extracted: list[ExtractedPerson],
        default_hospital: str | None,
        default_state: str | None,
    ) -> int:
        source_file = normalize_source_file(source_file)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM records WHERE source_file = ?", (source_file,))
            for person in extracted:
                content = person.to_content()
                conn.execute(
                    """
                    INSERT INTO records (
                        source_file, hospital, state, full_name, cedula, content, content_lower
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_file,
                        person.hospital or default_hospital,
                        person.state or default_state,
                        person.full_name,
                        person.cedula,
                        content,
                        content.lower(),
                    ),
                )
            conn.execute(
                """
                INSERT INTO ingest_files (source_file, status, record_count, error_message, processed_at)
                VALUES (?, 'ok', ?, NULL, ?)
                ON CONFLICT(source_file) DO UPDATE SET
                    status = 'ok',
                    record_count = excluded.record_count,
                    error_message = NULL,
                    processed_at = excluded.processed_at
                """,
                (source_file, len(extracted), now),
            )
            conn.commit()
        self._backup()
        return len(extracted)

    def mark_file_failed(self, source_file: str, error: str) -> None:
        source_file = normalize_source_file(source_file)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ingest_files (source_file, status, record_count, error_message, processed_at)
                VALUES (?, 'failed', 0, ?, ?)
                ON CONFLICT(source_file) DO UPDATE SET
                    status = 'failed',
                    record_count = 0,
                    error_message = excluded.error_message,
                    processed_at = excluded.processed_at
                """,
                (source_file, error[:2000], now),
            )
            conn.commit()

    def ingest_status(self) -> dict[str, int | list[dict[str, str]]]:
        with self._connect() as conn:
            ok = conn.execute(
                "SELECT COUNT(*) AS c FROM ingest_files WHERE status = 'ok'"
            ).fetchone()["c"]
            failed = conn.execute(
                "SELECT COUNT(*) AS c FROM ingest_files WHERE status = 'failed'"
            ).fetchone()["c"]
            records = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
            failed_rows = conn.execute(
                """
                SELECT source_file, error_message, processed_at
                FROM ingest_files WHERE status = 'failed'
                ORDER BY processed_at DESC LIMIT 20
                """
            ).fetchall()

        return {
            "files_ok": int(ok),
            "files_failed": int(failed),
            "records_total": int(records),
            "recent_failures": [
                {
                    "source_file": row["source_file"],
                    "error": row["error_message"] or "",
                    "processed_at": row["processed_at"],
                }
                for row in failed_rows
            ],
        }

    def _backup(self) -> None:
        if not self._db_path.exists():
            return
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self._backup_dir / f"search_{stamp}.db"
        shutil.copy2(self._db_path, target)

        backups = sorted(self._backup_dir.glob("search_*.db"), reverse=True)
        for old in backups[self._backup_keep :]:
            old.unlink(missing_ok=True)
