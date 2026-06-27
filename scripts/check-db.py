import sqlite3
from pathlib import Path

db = Path("search.db")
print("KB:", db.stat().st_size // 1024 if db.exists() else 0)
c = sqlite3.connect(db)
print("personas:", c.execute("SELECT COUNT(*) FROM records").fetchone()[0])
print("archivos OK:", c.execute("SELECT COUNT(*) FROM ingest_files WHERE status='ok'").fetchone()[0])
print("fallidos:", c.execute("SELECT COUNT(*) FROM ingest_files WHERE status='failed'").fetchone()[0])
