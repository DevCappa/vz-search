from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vz_search.domain.entities import ExtractedPerson


class DocumentAnalyzerPort(Protocol):
    def analyze_file(
        self,
        path: Path,
        source_hint: str,
        hospital_hint: str | None,
    ) -> tuple[list[ExtractedPerson], str | None]:
        """
        Una pasada de IA sobre el archivo.
        Retorna (personas extraídas, error opcional).
        """
        ...
