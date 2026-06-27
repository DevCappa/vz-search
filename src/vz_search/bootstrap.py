from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vz_search.application.ingest_use_case import IngestUseCase
from vz_search.application.search_use_case import SearchUseCase
from vz_search.config import Settings
from vz_search.domain.entities import IngestStats
from vz_search.domain.ports.record_repository import RecordRepository
from vz_search.infrastructure.cache.ttl_memory_cache import TtlMemoryCache
from vz_search.infrastructure.persistence.in_memory_record_repository import InMemoryRecordRepository
from vz_search.infrastructure.persistence.db_bootstrap import bootstrap_database
from vz_search.infrastructure.persistence.snapshot_migration import migrate_snapshot_to_sqlite
from vz_search.infrastructure.persistence.sqlite_person_index import SqlitePersonIndex

_MEMORY_STORE = InMemoryRecordRepository()


class SearchOnlyIngestor:
    """Railway/producción: solo búsqueda. Indexar en PC y subir search.db."""

    def __init__(self, index: SqlitePersonIndex) -> None:
        self._index = index

    def ingest(self, *, full_rebuild: bool = False) -> IngestStats:
        return IngestStats(
            files=0,
            records=self._index.count(),
            errors=(
                "Ingestión desactivada en servidor. "
                "Indexa en tu PC (python scripts/ingest.py) y sube search.db "
                "con PUT /api/v1/ingest/database?token=...",
            ),
            ai_calls=0,
        )


def _build_analyzer(settings: Settings):
    from vz_search.infrastructure.ai.gemini_analyzer import GeminiDocumentAnalyzer
    from vz_search.infrastructure.ai.hybrid_analyzer import HybridDocumentAnalyzer
    from vz_search.infrastructure.ai.local_analyzer import LocalDocumentAnalyzer
    from vz_search.infrastructure.ai.ollama_analyzer import OllamaDocumentAnalyzer

    local = LocalDocumentAnalyzer()
    provider = settings.ai_provider.lower()

    if provider == "ollama":
        ollama = OllamaDocumentAnalyzer(
            model=settings.ollama_model,
            host=settings.ollama_host,
            max_pdf_pages=settings.max_pdf_pages,
        )
        return HybridDocumentAnalyzer(ollama, local), "ollama"

    if provider == "gemini" and settings.gemini_api_key:
        gemini = GeminiDocumentAnalyzer(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            max_pdf_pages=settings.max_pdf_pages,
        )
        return HybridDocumentAnalyzer(gemini, local), "gemini"

    if provider == "local":
        return local, "local"

    if settings.gemini_api_key:
        gemini = GeminiDocumentAnalyzer(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            max_pdf_pages=settings.max_pdf_pages,
        )
        return HybridDocumentAnalyzer(gemini, local), "gemini+local"

    ollama = OllamaDocumentAnalyzer(
        model=settings.ollama_model,
        host=settings.ollama_host,
        max_pdf_pages=settings.max_pdf_pages,
    )
    return HybridDocumentAnalyzer(ollama, local), "ollama+local"


@dataclass
class Container:
    settings: Settings
    search_use_case: SearchUseCase
    ingest_use_case: IngestUseCase
    record_repository: RecordRepository
    ingest_mode: str
    storage_mode: str
    person_index: SqlitePersonIndex | None = None


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    data_dir = Path(settings.data_dir)
    cache = TtlMemoryCache(maxsize=settings.cache_max_size, ttl=settings.cache_ttl_seconds)
    person_index: SqlitePersonIndex | None = None

    if settings.storage == "sqlite":
        person_index = SqlitePersonIndex(
            db_path=Path(settings.db_path),
            backup_dir=Path(settings.backup_dir),
            backup_keep=settings.backup_keep,
        )
        bootstrap_database(Path(settings.db_path), settings.db_bootstrap_url)
        migrate_snapshot_to_sqlite(Path("index_snapshot.json"), person_index)
        repository: RecordRepository = person_index

        if settings.ingest_mode == "ai":
            from vz_search.infrastructure.ingestion.ai_ingestor import AiIngestor

            analyzer, ingest_mode = _build_analyzer(settings)
            ingestor = AiIngestor(
                data_dir=data_dir,
                index=person_index,
                analyzer=analyzer,
                request_delay_seconds=settings.ai_request_delay_seconds,
                incremental=settings.ingest_incremental,
            )
        else:
            ingestor = SearchOnlyIngestor(person_index)
            ingest_mode = "search-only"
        storage_mode = "sqlite"
    else:
        from vz_search.infrastructure.ingestion.memory_text_ingestor import MemoryTextIngestor

        repository = _MEMORY_STORE
        ingestor = MemoryTextIngestor(data_dir=data_dir, repository=_MEMORY_STORE)
        ingest_mode = "text"
        storage_mode = "memory"

    return Container(
        settings=settings,
        search_use_case=SearchUseCase(repository=repository, cache=cache),
        ingest_use_case=IngestUseCase(ingestor=ingestor, cache=cache),
        record_repository=repository,
        ingest_mode=ingest_mode,
        storage_mode=storage_mode,
        person_index=person_index,
    )
