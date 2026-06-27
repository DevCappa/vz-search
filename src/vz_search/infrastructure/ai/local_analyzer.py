from __future__ import annotations

from pathlib import Path
import fitz

from vz_search.domain.entities import ExtractedPerson
from vz_search.infrastructure.ai.json_parser import read_docx_text, read_text_file, read_xlsx_text
from vz_search.infrastructure.name_extraction import extract_persons_from_text

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


class LocalDocumentAnalyzer:
    """Extracción local sin IA: OCR para imágenes, texto para office/pdf."""

    def __init__(self) -> None:
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
        return self._ocr

    def analyze_file(
        self,
        path: Path,
        source_hint: str,
        hospital_hint: str | None,
    ) -> tuple[list[ExtractedPerson], str | None]:
        try:
            text = self._extract_text(path)
            if not text.strip():
                return [], "No se pudo extraer texto (OCR/texto vacío)"

            persons = extract_persons_from_text(text, hospital_hint)
            if not persons:
                return [], "No se identificaron nombres legibles en el documento"
            return persons, None
        except Exception as exc:  # noqa: BLE001
            return [], str(exc)

    def _extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            doc = fitz.open(path)
            parts = [page.get_text("text") for page in doc]
            doc.close()
            text = "\n".join(parts)
            if len(text.strip()) < 30:
                text = self._ocr_pdf(path)
            return text

        if suffix in IMAGE_SUFFIXES:
            return self._ocr_image(path)

        if suffix == ".docx":
            return read_docx_text(path)
        if suffix == ".xlsx":
            return read_xlsx_text(path)
        if suffix in {".txt", ".csv", ".md"}:
            return read_text_file(path)

        return ""

    def _ocr_image(self, path: Path) -> str:
        result, _ = self._get_ocr()(str(path))
        if not result:
            return ""
        return "\n".join(line[1] for line in result if len(line) > 1)

    def _ocr_pdf(self, path: Path) -> str:
        doc = fitz.open(path)
        parts: list[str] = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img_path = path.with_suffix(f".page{page.number}.png")
            pix.save(str(img_path))
            parts.append(self._ocr_image(img_path))
            img_path.unlink(missing_ok=True)
        doc.close()
        return "\n".join(parts)

