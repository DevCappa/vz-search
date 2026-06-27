from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersonRecordSchema(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 42,
                "source_file": "HOSPITAL PEREZ CARREÑO/lista.pdf",
                "hospital": "HOSPITAL PEREZ CARREÑO",
                "state": "Miranda",
                "full_name": "María González",
                "cedula": "V-12345678",
                "content": "María González | Cédula: V-12345678 | Condición: estable",
                "score": 95,
            }
        }
    )

    id: int
    source_file: str
    hospital: str | None = None
    state: str | None = None
    full_name: str | None = None
    cedula: str | None = None
    content: str
    score: int | None = Field(default=None, description="Coincidencia difusa 0-100")


class SearchResponseSchema(BaseModel):
    query: str = ""
    hospital: str = ""
    state: str = ""
    limit: int = 50
    total: int
    cached: bool
    results: list[PersonRecordSchema]


class HealthResponseSchema(BaseModel):
    status: str
    records_indexed: int
    storage: str = Field(description="`sqlite` = disco durable")
    ingest_mode: str = Field(description="`ai` o `text`")
    ai_configured: bool
    cache_ttl_seconds: int


class IngestResponseSchema(BaseModel):
    files: int = Field(description="Archivos procesados en esta ejecución")
    records: int = Field(description="Total de personas en el índice")
    ai_calls: int = Field(default=0, description="Llamadas a Gemini en esta ejecución")
    skipped: int = Field(default=0, description="Archivos ya indexados (modo incremental)")
    pending: int = Field(default=0, description="Archivos pendientes en esta ejecución")
    errors: list[str] = Field(default_factory=list)
    message: str = ""


class IngestStatusSchema(BaseModel):
    files_ok: int
    files_failed: int
    records_total: int
    storage: str
    db_path: str
    backup_dir: str
    recent_failures: list[dict[str, str]] = Field(default_factory=list)


class ErrorSchema(BaseModel):
    detail: str
