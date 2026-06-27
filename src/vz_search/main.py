"""Punto de entrada ASGI para uvicorn."""

from vz_search.adapters.api.app import create_app

app = create_app()
