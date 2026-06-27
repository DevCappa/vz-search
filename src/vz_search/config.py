from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VZ_SEARCH_", env_file=".env", extra="ignore")

    data_dir: str = "data"
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, validation_alias=AliasChoices("VZ_SEARCH_API_PORT", "PORT"))
    http_cache_max_age: int = 60
    enable_docs: bool = True
    env: str = "development"
    cache_ttl_seconds: int = 300
    cache_max_size: int = 1024

    # IA — una pasada al ingestar (Gemini gratis: https://aistudio.google.com/apikey)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    max_pdf_pages: int = 15
    ingest_mode: str = "ai"  # ai | text
    auto_ingest_on_startup: bool = False
    ingest_incremental: bool = True
    ai_request_delay_seconds: float = 7.0

    # Persistencia durable (recomendado para ~20MB de documentos)
    db_path: str = "search.db"
    storage: str = "sqlite"  # sqlite | memory
    backup_dir: str = "backups"
    backup_keep: int = 5
    db_bootstrap_url: str = ""  # URL directa a search.db pre-indexado (Google Drive, etc.)
