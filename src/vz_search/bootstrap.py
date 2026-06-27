from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vz_search.application.ingest_use_case import IngestUseCase
from vz_search.application.search_use_case import SearchUseCase
from vz_search.config import Settings
from vz_search.domain.ports.record_repository import RecordRepository
from vz_search.infrastructure.ai.gemini_analyzer import GeminiDocumentAnalyzer
from vz_search.infrastructure.cache.ttl_memory_cache import TtlMemoryCache
from vz_search.infrastructure.ingestion.ai_ingestor import AiIngestor
from vz_search.infrastructure.ingestion.memory_text_ingestor import MemoryTextIngestor
from vz_search.infrastructure.persistence.in_memory_record_repository import InMemoryRecordRepository
from vz_search.infrastructure.persistence.db_bootstrap import bootstrap_database
from vz_search.infrastructure.persistence.snapshot_migration import migrate_snapshot_to_sqlite
from vz_search.infrastructure.persistence.sqlite_person_index import SqlitePersonIndex

_MEMORY_STORE = InMemoryRecordRepository()


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

        if settings.ingest_mode == "ai" and settings.gemini_api_key:
            analyzer = GeminiDocumentAnalyzer(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
                max_pdf_pages=settings.max_pdf_pages,
            )
            ingestor = AiIngestor(
                data_dir=data_dir,
                index=person_index,
                analyzer=analyzer,
                request_delay_seconds=settings.ai_request_delay_seconds,
                incremental=settings.ingest_incremental,
            )
            ingest_mode = "ai"
        else:
            ingestor = MemoryTextIngestor(data_dir=data_dir, repository=_MEMORY_STORE)
            ingest_mode = "text"
        storage_mode = "sqlite"
    else:
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
