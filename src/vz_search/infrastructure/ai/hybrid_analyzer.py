from __future__ import annotations

from pathlib import Path

from vz_search.domain.entities import ExtractedPerson
from vz_search.domain.ports.document_analyzer import DocumentAnalyzerPort
from vz_search.infrastructure.ai.gemini_analyzer import GeminiDocumentAnalyzer
from vz_search.infrastructure.ai.local_analyzer import LocalDocumentAnalyzer

QUOTA_ERRORS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "quota", "connection", "refused", "not found", "model")


class HybridDocumentAnalyzer:
    """Intenta Gemini; si cuota agotada, usa OCR/texto local (gratis, sin API)."""

    def __init__(self, gemini: GeminiDocumentAnalyzer, local: LocalDocumentAnalyzer) -> None:
        self._gemini = gemini
        self._local = local
        self._gemini_down = False

    def analyze_file(
        self,
        path: Path,
        source_hint: str,
        hospital_hint: str | None,
    ) -> tuple[list[ExtractedPerson], str | None]:
        if not self._gemini_down:
            persons, error = self._gemini.analyze_file(path, source_hint, hospital_hint)
            if not error and persons:
                return persons, None
            if error and any(token in error.upper() for token in QUOTA_ERRORS):
                self._gemini_down = True
            elif not error:
                return persons, None
            elif error and "no encontró" not in error.lower():
                # Otros errores: probar local igual
                pass

        persons, local_error = self._local.analyze_file(path, source_hint, hospital_hint)
        if persons:
            return persons, None
        return [], local_error or "Gemini sin cuota y OCR local no extrajo personas"
