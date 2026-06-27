from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])

sys.path.insert(0, str(ROOT / "src"))

from vz_search.bootstrap import build_container  # noqa: E402


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Indexar documentos en search.db")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Borrar índice y reprocesar todos los archivos",
    )
    args = parser.parse_args()

    container = build_container()
    stats = container.ingest_use_case.execute(full_rebuild=args.full)
    print(json.dumps(asdict(stats), indent=2, ensure_ascii=False))
    print(f"\nBase de datos: {container.settings.db_path}")


if __name__ == "__main__":
    main()
