from __future__ import annotations

import urllib.request
from pathlib import Path


def bootstrap_database(db_path: Path, url: str) -> bool:
    """Descarga search.db pre-indexado si no existe localmente."""
    if not url.strip():
        return False
    if db_path.exists() and db_path.stat().st_size > 1024:
        return False

    db_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "vz-search/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        db_path.write_bytes(response.read())
    return db_path.exists()
