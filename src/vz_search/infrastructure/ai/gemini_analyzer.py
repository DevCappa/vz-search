from __future__ import annotations

import time
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

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

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TEXT_SUFFIXES = {".txt", ".csv", ".md", ".docx", ".xlsx"}
MAX_RETRIES = 5


class GeminiDocumentAnalyzer:
    """Una llamada de IA por archivo. Soporta keys nuevas (AQ.) y legacy (AIzaSy)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-lite",
        max_pdf_pages: int = 15,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_name = model
        self._max_pdf_pages = max_pdf_pages

    def _generate(self, parts: list[types.Part]) -> str:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                return response.text or ""
            except genai_errors.ClientError as exc:
                last_error = exc
                if exc.code not in {429, 503} or attempt == MAX_RETRIES - 1:
                    raise
                wait = min(60, 7 * (attempt + 1))
                time.sleep(wait)
        raise last_error or RuntimeError("Error desconocido en Gemini")

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
            parts: list[types.Part] = [types.Part.from_text(text=prompt)]
            suffix = path.suffix.lower()

            if suffix == ".pdf":
                for png in pdf_pages_as_png_bytes(path, self._max_pdf_pages):
                    parts.append(types.Part.from_bytes(data=png, mime_type="image/png"))
            elif suffix in IMAGE_SUFFIXES:
                mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else f"image/{suffix.lstrip('.')}"
                for raw in load_image_bytes(path):
                    parts.append(types.Part.from_bytes(data=raw, mime_type=mime))
            elif suffix in TEXT_SUFFIXES:
                if suffix == ".docx":
                    content = read_docx_text(path)
                elif suffix == ".xlsx":
                    content = read_xlsx_text(path)
                else:
                    content = read_text_file(path)
                parts.append(types.Part.from_text(text=f"\n\nContenido del archivo:\n{content}"))
            else:
                return [], f"Formato no soportado: {suffix}"

            if len(parts) == 1:
                return [], "No se pudo leer contenido del archivo"

            raw_text = self._generate(parts)
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
                        notes=p.notes,
                    )
                    for p in persons
                ]

            return persons, None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)
