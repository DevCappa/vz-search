from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse

from vz_search.adapters.api.dependencies import get_container
from vz_search.adapters.api.openapi import OPENAPI_DESCRIPTION, OPENAPI_TAGS
from vz_search.adapters.api.routes import router
from vz_search.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    docs_enabled = settings.enable_docs

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        container = get_container()
        if container.settings.auto_ingest_on_startup and container.record_repository.count() == 0:
            container.ingest_use_case.execute()
        yield

    app = FastAPI(
        title="VZ Search API",
        description=OPENAPI_DESCRIPTION,
        version="2.0.0",
        openapi_tags=OPENAPI_TAGS,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
        contact={
            "name": "VZ Search — SISMO 2026",
        },
        license_info={
            "name": "Uso humanitario",
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(router)

    if docs_enabled:

        @app.get("/docs", include_in_schema=False)
        async def swagger_ui() -> HTMLResponse:
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title="VZ Search API — Swagger",
                swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
                swagger_ui_parameters={
                    "docExpansion": "list",
                    "defaultModelsExpandDepth": 1,
                    "tryItOutEnabled": True,
                    "persistAuthorization": True,
                    "displayRequestDuration": True,
                    "filter": True,
                },
            )

        @app.get("/redoc", include_in_schema=False)
        async def redoc_ui() -> HTMLResponse:
            return get_redoc_html(
                openapi_url="/openapi.json",
                title="VZ Search API — ReDoc",
            )

    @app.get("/", tags=["meta"], summary="Información de la API")
    def root() -> dict[str, str | bool]:
        return {
            "message": "VZ Search API — memoria volátil + IA en ingestión",
            "environment": settings.env,
            "swagger": "/docs" if docs_enabled else None,
            "redoc": "/redoc" if docs_enabled else None,
            "openapi": "/openapi.json" if docs_enabled else None,
            "health": "/api/v1/health",
            "search_example": "/api/v1/search?q=Gonzalez",
        }

    return app
