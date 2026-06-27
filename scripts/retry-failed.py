"""Reprocesa archivos fallidos en ingest_files (requiere Ollama o Gemini en .env)."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

sys.path.insert(0, str(ROOT / "src"))

from vz_search.bootstrap import build_container  # noqa: E402


def normalize_path(p: str) -> str:
    return p.replace("\\", "/")


def main() -> None:
    db_path = ROOT / "search.db"
    conn = sqlite3.connect(db_path)
    failed = conn.execute(
        "SELECT DISTINCT source_file FROM ingest_files WHERE status = 'failed'"
    ).fetchall()
    conn.close()

    if not failed:
        print("No hay archivos fallidos.")
        return

    print("Fallidos:", len(failed))
    for (source_file,) in failed:
        print(" -", source_file)

    container = build_container()
    data_dir = Path(container.settings.data_dir)
    analyzer, mode = __import__(
        "vz_search.bootstrap", fromlist=["_build_analyzer"]
    )._build_analyzer(container.settings)
    print(f"Analizador: {mode}")

    from vz_search.infrastructure.ingestion.ai_ingestor import AiIngestor
    from vz_search.infrastructure.path_metadata import extract_file_context, enrich_person_notes
    from vz_search.domain.entities import ExtractedPerson

    index = container.person_index
    assert index is not None

    for (source_file,) in failed:
        rel = normalize_path(source_file)
        path = data_dir / Path(rel)
        if not path.exists():
            # Probar variantes de separador
            path = data_dir / Path(source_file)
        if not path.exists():
            print(f"NO EN DISCO: {source_file}")
            continue

        ctx = extract_file_context(path, data_dir)
        print(f"\nProcesando: {ctx.source_file}")

        persons, error = analyzer.analyze_file(
            path=path,
            source_hint=ctx.source_file,
            hospital_hint=ctx.hospital,
        )
        if error:
            index.mark_file_failed(ctx.source_file, error)
            print(f"  ERROR: {error}")
            continue
        if not persons:
            index.mark_file_failed(ctx.source_file, "IA no encontró personas")
            print("  Sin personas")
            continue

        enriched = [
            ExtractedPerson(
                full_name=p.full_name,
                hospital=p.hospital or ctx.hospital,
                state=p.state or ctx.state,
                cedula=p.cedula,
                age=p.age,
                condition=p.condition,
                notes=enrich_person_notes(p.notes, ctx),
            )
            for p in persons
        ]
        added = index.replace_file_records(
            source_file=ctx.source_file,
            extracted=enriched,
            default_hospital=ctx.hospital,
            default_state=ctx.state,
        )
        # Limpiar entrada duplicada con otro separador
        alt = source_file.replace("/", "\\") if "/" in source_file else source_file.replace("\\", "/")
        if alt != ctx.source_file:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM ingest_files WHERE source_file = ?", (alt,))
            conn.commit()
            conn.close()

        print(f"  OK: {added} personas")

    stats = index.ingest_status()
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
