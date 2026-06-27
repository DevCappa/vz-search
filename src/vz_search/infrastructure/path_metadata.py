from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vz_search.infrastructure.text_processing import detect_state


@dataclass(frozen=True, slots=True)
class FileContext:
    """Metadatos extraídos de la ruta del archivo (data descentralizada)."""
    source_file: str
    hospital: str
    state: str | None
    location: str  # carpeta o sitio (campo de golf, etc.)
    file_name: str


def extract_file_context(path: Path, data_dir: Path) -> FileContext:
    try:
        rel = path.relative_to(data_dir)
    except ValueError:
        rel = path

    parts = rel.parts
    hospital = parts[0].replace("_", " ").strip() if len(parts) > 1 else path.stem
    location = hospital
    file_name = path.name

    # Si hay subcarpetas, la primera sigue siendo el hospital/centro principal
    state = detect_state(hospital) or detect_state(str(rel)) or detect_state(file_name)

    return FileContext(
        source_file=str(rel).replace("\\", "/"),
        hospital=hospital,
        state=state,
        location=location,
        file_name=file_name,
    )


def enrich_person_notes(notes: str | None, ctx: FileContext) -> str:
    """Conserva hospital, estado y origen del archivo en cada registro."""
    meta_parts = [f"Hospital: {ctx.hospital}"]
    if ctx.state:
        meta_parts.append(f"Estado: {ctx.state}")
    meta_parts.append(f"Archivo: {ctx.file_name}")
    meta = " | ".join(meta_parts)
    if notes and notes.strip():
        return f"{meta} | {notes.strip()}"
    return meta
