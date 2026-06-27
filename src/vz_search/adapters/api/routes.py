from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse

from vz_search.adapters.api.dependencies import get_container
from vz_search.adapters.api.openapi import SEARCH_EXAMPLES
from vz_search.adapters.api.schemas import (
    ErrorSchema,
    HealthResponseSchema,
    IngestResponseSchema,
    IngestStatusSchema,
    SearchResponseSchema,
    UploadDbResponseSchema,
)
from vz_search.bootstrap import Container
from vz_search.domain.entities import SearchQuery
from vz_search.infrastructure.ingestion.ai_ingestor import count_data_files

router = APIRouter(prefix="/api/v1")


def _safe_data_path(data_dir: Path, source: str) -> Path | None:
    rel = source.replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    path = (data_dir / rel).resolve()
    try:
        path.relative_to(data_dir.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def _source_image_url(source_file: str) -> str:
    return f"/api/v1/files?source={quote(source_file, safe='')}"


@router.get(
    "/health",
    response_model=HealthResponseSchema,
    tags=["sistema"],
    summary="Estado del servicio",
    description="Comprueba si la API está activa, cuántas personas hay indexadas y si la IA está configurada.",
    responses={
        200: {"description": "Servicio operativo"},
    },
)
def health(container: Container = Depends(get_container)) -> HealthResponseSchema:
    return HealthResponseSchema(
        status="ok",
        records_indexed=container.record_repository.count(),
        storage=container.storage_mode,
        ingest_mode=container.ingest_mode,
        ai_configured=bool(container.settings.gemini_api_key),
        cache_ttl_seconds=container.settings.cache_ttl_seconds,
    )


@router.get(
    "/search",
    response_model=SearchResponseSchema,
    tags=["búsqueda"],
    summary="Buscar persona",
    description=(
        "Busca en memoria volátil por **nombre/apellido**, **hospital** y/o **estado**. "
        "Indica al menos un criterio. No consume cuota de Gemini."
    ),
    responses={
        200: {"description": "Búsqueda exitosa (puede devolver 0 resultados)"},
        400: {"model": ErrorSchema, "description": "Faltan criterios de búsqueda"},
        503: {"model": ErrorSchema, "description": "No hay datos — ejecuta POST /ingest primero"},
    },
    openapi_extra={"examples": SEARCH_EXAMPLES},
)
def search(
    response: Response,
    q: str = Query(
        default="",
        description="Nombre o apellido (prueba solo apellido si no hay coincidencias)",
        examples={
            "apellido": {"summary": "Apellido", "value": "Gonzalez"},
            "nombre_completo": {"summary": "Nombre completo", "value": "María González"},
        },
    ),
    hospital: str = Query(
        default="",
        description="Parte del nombre del hospital",
        examples={"perez": {"summary": "Pérez Carreño", "value": "Perez"}},
    ),
    state: str = Query(
        default="",
        description="Estado venezolano",
        examples={"miranda": {"summary": "Miranda", "value": "Miranda"}},
    ),
    limit: int = Query(default=50, ge=1, le=200, description="Máximo de resultados"),
    container: Container = Depends(get_container),
) -> SearchResponseSchema:
    query = SearchQuery(name=q, hospital=hospital, state=state, limit=limit)

    if query.is_empty():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar al menos un criterio: q, hospital o state",
        )

    if container.record_repository.count() == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No hay datos en memoria. Ejecuta POST /api/v1/ingest "
                "(hará una pasada de IA sobre los PDFs/imágenes en ./data/)"
            ),
        )

    result = container.search_use_case.execute(query)

    response.headers["X-Cache"] = "HIT" if result.cached else "MISS"
    response.headers["Cache-Control"] = f"public, max-age={container.settings.http_cache_max_age}"

    from vz_search.adapters.api.schemas import PersonRecordSchema

    return SearchResponseSchema(
        query=q,
        hospital=hospital,
        state=state,
        limit=limit,
        total=result.total,
        cached=result.cached,
        results=[
            PersonRecordSchema(
                id=record.id,
                source_file=record.source_file,
                hospital=record.hospital,
                state=record.state,
                full_name=record.full_name,
                cedula=record.cedula,
                content=record.content,
                score=record.score,
                source_image_url=_source_image_url(record.source_file),
            )
            for record in result.records
        ],
    )


@router.get(
    "/files",
    tags=["búsqueda"],
    summary="Ver imagen o documento original",
    description=(
        "Sirve el archivo fuente desde `./data/` (solo si existe en el servidor). "
        "En Railway normalmente no está la carpeta data — indexa en PC y sube search.db."
    ),
    responses={
        200: {"description": "Archivo binario (jpeg, pdf, etc.)"},
        404: {"model": ErrorSchema, "description": "Archivo no disponible en este servidor"},
    },
)
def get_source_file(
    source: str = Query(description="Ruta relativa, ej. HOSPITAL PEREZ CARREÑO/foto.jpeg"),
    container: Container = Depends(get_container),
) -> FileResponse:
    data_dir = Path(container.settings.data_dir)
    path = _safe_data_path(data_dir, source)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado en data/")
    return FileResponse(path)


@router.get(
    "/ingest/status",
    response_model=IngestStatusSchema,
    tags=["ingestión"],
    summary="Progreso de indexación",
    description="Muestra cuántos archivos van OK, cuántos fallaron y el total de personas en disco.",
)
def ingest_status(container: Container = Depends(get_container)) -> IngestStatusSchema:
    data_dir = Path(container.settings.data_dir)
    files_in_data = count_data_files(data_dir)

    if container.person_index is None:
        return IngestStatusSchema(
            files_ok=0,
            files_failed=0,
            records_total=container.record_repository.count(),
            files_in_data_dir=files_in_data,
            data_dir=str(data_dir),
            storage=container.storage_mode,
            db_path=container.settings.db_path,
            backup_dir=container.settings.backup_dir,
        )

    status = container.person_index.ingest_status()
    return IngestStatusSchema(
        files_ok=int(status["files_ok"]),
        files_failed=int(status["files_failed"]),
        records_total=int(status["records_total"]),
        files_in_data_dir=files_in_data,
        data_dir=str(data_dir),
        storage=container.storage_mode,
        db_path=container.settings.db_path,
        backup_dir=container.settings.backup_dir,
        recent_failures=list(status["recent_failures"]),  # type: ignore[arg-type]
    )


@router.post(
    "/ingest",
    response_model=IngestResponseSchema,
    tags=["ingestión"],
    summary="Indexar documentos (una pasada IA)",
    description=(
        "Procesa archivos pendientes de `./data/` con Gemini. "
        "**Modo incremental (default):** solo archivos nuevos o que fallaron antes. "
        "Espera ~7 s entre llamadas para respetar cuota gratis. "
        "Usa `full=true` para reprocesar todo desde cero."
    ),
    responses={
        200: {"description": "Ingestión completada (revisa `errors` para archivos fallidos)"},
        400: {"model": ErrorSchema, "description": "Falta API key de Gemini"},
    },
)
def ingest(
    full: bool = Query(
        default=False,
        description="Si true, borra el índice y reprocesa todo. Si false, solo archivos nuevos/fallidos.",
    ),
    container: Container = Depends(get_container),
) -> IngestResponseSchema:
    if container.ingest_mode == "ai" and not container.settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configura VZ_SEARCH_GEMINI_API_KEY en .env (gratis en aistudio.google.com/apikey)",
        )

    if container.ingest_mode == "search-only":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestión solo en PC local. Sube search.db con PUT /api/v1/ingest/database?token=...",
        )

    stats = container.ingest_use_case.execute(full_rebuild=full)
    mode = "completa" if full else "incremental"
    mode_msg = (
        f"Ingestión IA {mode}: {stats.ai_calls} llamadas, "
        f"+{stats.files} archivos nuevos, {stats.records} personas en índice."
        if container.ingest_mode == "ai"
        else f"Ingestión texto: {stats.records} registros en memoria."
    )
    if stats.errors:
        mode_msg += f" {len(stats.errors)} archivo(s) con error — vuelve a ejecutar más tarde."

    return IngestResponseSchema(
        files=stats.files,
        records=stats.records,
        ai_calls=stats.ai_calls,
        skipped=stats.skipped,
        pending=stats.pending,
        errors=list(stats.errors),
        message=mode_msg,
    )


@router.put(
    "/ingest/database",
    response_model=UploadDbResponseSchema,
    tags=["ingestión"],
    summary="Subir search.db indexado (Railway)",
    description=(
        "Sube search.db como cuerpo binario (application/octet-stream). "
        "Requiere token = VZ_SEARCH_UPLOAD_TOKEN. "
        "curl -X PUT 'URL?token=SECRET' --data-binary @search.db"
    ),
)
async def upload_database(
    request: Request,
    token: str = Query(description="Token de seguridad (VZ_SEARCH_UPLOAD_TOKEN)"),
    container: Container = Depends(get_container),
) -> UploadDbResponseSchema:
    if not container.settings.upload_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configura VZ_SEARCH_UPLOAD_TOKEN en Railway antes de subir la BD",
        )
    if token != container.settings.upload_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token inválido")

    db_path = Path(container.settings.db_path)
    content = await request.body()
    if len(content) < 1024:
        raise HTTPException(status_code=400, detail="Archivo demasiado pequeño — ¿search.db vacío?")

    for suffix in ("-wal", "-shm"):
        extra = Path(str(db_path) + suffix)
        if extra.exists():
            extra.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_bytes(content)

    container.search_use_case._cache.clear()  # noqa: SLF001
    total = container.record_repository.count()

    return UploadDbResponseSchema(
        records_total=total,
        db_path=str(db_path),
        bytes_received=len(content),
        message=f"Base de datos cargada. {total} personas listas para buscar.",
    )
