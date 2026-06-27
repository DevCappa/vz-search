from __future__ import annotations

import sqlite3
from pathlib import Path

from vz_search.domain.entities import PersonRecord, SearchQuery
from vz_search.infrastructure.text_processing import build_fts_query, rank_by_name


class SqliteRecordRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def clear(self) -> None:
        if self._db_path.exists():
            self._db_path.unlink()

    def add_many(self, records: list[PersonRecord]) -> None:
        raise NotImplementedError("Use FileIngestor para SQLite")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def count(self) -> int:
        if not self._db_path.exists():
            return 0
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM records").fetchone()
            return int(row["total"]) if row else 0

    def search(self, query: SearchQuery) -> list[PersonRecord]:
        if not self._db_path.exists():
            return []

        fts_query = build_fts_query(query.name)
        clauses: list[str] = []
        params: list[str | int] = []

        if fts_query:
            clauses.append(
                "id IN (SELECT rowid FROM records_fts WHERE records_fts MATCH ?)"
            )
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
            SELECT id, source_file, hospital, state, content
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
                content=row["content"],
            )
            for row in rows
        ]

        return rank_by_name(records, query.name, query.limit)
