from __future__ import annotations

import base64
from pathlib import Path

import ollama

from vz_search.domain.entities import ExtractedPerson
from vz_search.infrastructure.ai.json_parser import (
    load_image_bytes,
    parse_persons_json,
    pdf_pages_as_png_bytes,
    read_docx_text,
    read_text_file,
    read_xlsx_text,
)
from vz_search.infrastructure.ai.prompts import EXTRACTION_PROMPT
from vz_search.infrastructure.path_metadata import enrich_person_notes

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TEXT_SUFFIXES = {".txt", ".csv", ".md", ".docx", ".xlsx"}


class OllamaDocumentAnalyzer:
    """IA local con Ollama — usa GPU/CPU de tu PC, sin cuota en la nube."""

    def __init__(
        self,
        model: str = "llama3.2-vision",
        host: str = "http://localhost:11434",
        max_pdf_pages: int = 5,
    ) -> None:
        self._model = model
        self._client = ollama.Client(host=host)
        self._max_pdf_pages = max_pdf_pages

    def analyze_file(
        self,
        path: Path,
        source_hint: str,
        hospital_hint: str | None,
    ) -> tuple[list[ExtractedPerson], str | None]:
        try:
            prompt = EXTRACTION_PROMPT.format(
                source_hint=source_hint,
                hospital_hint=hospital_hint or "desconocido",
            )
            suffix = path.suffix.lower()
            images: list[str] = []

            if suffix == ".pdf":
                for png in pdf_pages_as_png_bytes(path, self._max_pdf_pages):
                    images.append(base64.b64encode(png).decode())
            elif suffix in IMAGE_SUFFIXES:
                for raw in load_image_bytes(path):
                    images.append(base64.b64encode(raw).decode())
            elif suffix in TEXT_SUFFIXES:
                if suffix == ".docx":
                    text = read_docx_text(path)
                elif suffix == ".xlsx":
                    text = read_xlsx_text(path)
                else:
                    text = read_text_file(path)
                prompt = f"{prompt}\n\nContenido del archivo:\n{text}"
            else:
                return [], f"Formato no soportado: {suffix}"

            message: dict = {"role": "user", "content": prompt}
            if images:
                message["images"] = images

            response = self._client.chat(
                model=self._model,
                messages=[message],
                options={"temperature": 0.1},
            )
            raw_text = response["message"]["content"]
            persons = parse_persons_json(raw_text)

            if hospital_hint:
                persons = [
                    ExtractedPerson(
                        full_name=p.full_name,
                        hospital=p.hospital or hospital_hint,
                        state=p.state,
                        cedula=p.cedula,
                        age=p.age,
                        condition=p.condition,
                        notes=enrich_person_notes(
                            p.notes,
                            _ctx_from_hint(source_hint, hospital_hint, p.state),
                        ),
                    )
                    for p in persons
                ]

            return persons, None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)


def _ctx_from_hint(source_hint: str, hospital: str | None, state: str | None):
    from vz_search.infrastructure.path_metadata import FileContext

    return FileContext(
        source_file=source_hint,
        hospital=hospital or "desconocido",
        state=state,
        location=hospital or "desconocido",
        file_name=Path(source_hint).name,
    )
