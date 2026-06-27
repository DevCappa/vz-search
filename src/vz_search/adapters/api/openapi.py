from __future__ import annotations

OPENAPI_TAGS = [
    {
        "name": "sistema",
        "description": "Estado del servicio y metadatos.",
    },
    {
        "name": "ingestión",
        "description": (
            "Carga documentos desde `./data/` con **una pasada de IA**. "
            "Los datos quedan en memoria volátil hasta reiniciar el servidor."
        ),
    },
    {
        "name": "búsqueda",
        "description": (
            "Consultas rápidas por nombre, apellido, hospital o estado. "
            "**No consume IA** — solo busca en memoria."
        ),
    },
    {
        "name": "meta",
        "description": "Información general de la API.",
    },
]

OPENAPI_DESCRIPTION = """
## VZ Search — SISMO 2026 Venezuela

API REST para localizar personas en listados hospitalarios.

### Flujo recomendado (pruebas en Swagger)

1. **`GET /api/v1/health`** — Verifica que la API esté arriba y cuántos registros hay en memoria.
2. **`POST /api/v1/ingest`** — Procesa PDFs/imágenes de `./data/` (usa Gemini, tarda varios minutos).
3. **`GET /api/v1/search`** — Busca por nombre, hospital o estado.

### Headers de respuesta (búsqueda)

| Header | Valores | Significado |
|--------|---------|-------------|
| `X-Cache` | `HIT` / `MISS` | Si la respuesta vino del cache en memoria |
| `Cache-Control` | `public, max-age=60` | Cache HTTP para proxies |

### Entornos

| Variable | Desarrollo | Producción |
|----------|------------|------------|
| `VZ_SEARCH_ENABLE_DOCS` | `true` (default) | `false` |
| `VZ_SEARCH_ENV` | `development` | `production` |

### Autenticación

Esta versión **no requiere auth** (uso interno/humanitario).  
En producción se recomienda poner un reverse proxy con API key o VPN.
"""

SEARCH_EXAMPLES = {
    "por_apellido": {
        "summary": "Buscar por apellido",
        "description": "Prueba con solo el apellido si no conoces el nombre completo.",
        "value": {"q": "Gonzalez", "hospital": "", "state": "", "limit": 20},
    },
    "nombre_y_hospital": {
        "summary": "Nombre + hospital",
        "value": {"q": "María", "hospital": "Perez", "state": "", "limit": 10},
    },
    "por_estado": {
        "summary": "Filtrar por estado",
        "value": {"q": "Rodriguez", "hospital": "", "state": "Miranda", "limit": 50},
    },
}
