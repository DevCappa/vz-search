"""Normaliza rutas duplicadas en ingest_files (\\ vs /)."""
import sqlite3
from pathlib import Path

db = Path("search.db")
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row

rows = conn.execute("SELECT source_file, status, record_count, error_message, processed_at FROM ingest_files").fetchall()
by_norm: dict[str, list] = {}
for row in rows:
    norm = row["source_file"].replace("\\", "/")
    by_norm.setdefault(norm, []).append(row)

merged = 0
deleted = 0
for norm, group in by_norm.items():
    if len(group) == 1:
        if group[0]["source_file"] != norm:
            conn.execute(
                "UPDATE ingest_files SET source_file = ? WHERE source_file = ?",
                (norm, group[0]["source_file"]),
            )
            conn.execute(
                "UPDATE records SET source_file = ? WHERE source_file = ?",
                (norm, group[0]["source_file"]),
            )
            merged += 1
        continue

    best = max(group, key=lambda r: (r["status"] == "ok", r["record_count"], r["processed_at"]))
    for row in group:
        if row["source_file"] != best["source_file"]:
            conn.execute("DELETE FROM ingest_files WHERE source_file = ?", (row["source_file"],))
            deleted += 1
    if best["source_file"] != norm:
        conn.execute(
            "UPDATE ingest_files SET source_file = ? WHERE source_file = ?",
            (norm, best["source_file"]),
        )
    conn.execute(
        "UPDATE records SET source_file = ? WHERE source_file IN ({})".format(
            ",".join("?" * len(group))
        ),
        (norm, *[r["source_file"] for r in group]),
    )
    merged += 1

conn.commit()
conn.close()
print(f"normalizados: {merged}, duplicados eliminados: {deleted}")
