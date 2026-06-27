# VZ Search — IA + memoria volátil

Búsqueda humanitaria para listados hospitalarios del sismo 2026 en Venezuela.

**Flujo:** una pasada de IA al ingestar PDFs/imágenes → datos normalizados en RAM → búsquedas instantáneas **sin volver a llamar a la IA**.

## Por qué IA + memoria volátil

Los documentos de Drive son PDFs escaneados (fotos), tablas distintas y formatos mezclados.  
**Gemini Flash** (gratis) lee imágenes y devuelve JSON coherente con nombre, hospital, estado, cédula, etc.

| Fase | Qué pasa | Dónde vive | IA |
|------|----------|------------|-----|
| `POST /ingest` | Lee cada archivo **una vez**, extrae personas | **`search.db` en disco** | ✅ Sí |
| `GET /search` | Busca por nombre/hospital/estado | SQLite + cache | ❌ No |

## Plan durable (~20 MB de documentos)

Los PDFs/imágenes (~20 MB) **no se guardan en la BD** — solo viven en `./data/`.  
Lo que importa son las **personas extraídas**, guardadas en SQLite:

| Archivo | Qué es | Se pierde al reiniciar? |
|---------|--------|------------------------|
| `./data/` | PDFs e imágenes originales | ❌ No (tus archivos) |
| `search.db` | Personas indexadas + log de ingestión | ❌ No |
| `backups/search_*.db` | Copia automática tras cada archivo OK | ❌ No |
| RAM | Solo cache de búsquedas | ✅ Sí (se regenera) |

### Flujo recomendado

1. **`POST /api/v1/ingest`** — incremental, 7 s entre archivos (cuota gratis)
2. **`GET /api/v1/ingest/status`** — ver progreso (OK / fallidos / total personas)
3. **`GET /api/v1/search`** — buscar (sin IA)
4. Repetir ingest mañana si hay error 429 — **no pierdes lo ya indexado**
5. Copia manual extra: `backups/` o duplica `search.db`

### Variables clave en `.env`

```env
VZ_SEARCH_STORAGE=sqlite
VZ_SEARCH_INGEST_INCREMENTAL=true
VZ_SEARCH_AI_REQUEST_DELAY_SECONDS=7
VZ_SEARCH_DB_PATH=search.db
VZ_SEARCH_BACKUP_DIR=backups
```

## Swagger — probar antes de producción

Con el servidor corriendo (`python run.py`):

| URL | Uso |
|-----|-----|
| **http://127.0.0.1:8000/docs** | Swagger UI interactivo |
| http://127.0.0.1:8000/redoc | Documentación legible |
| http://127.0.0.1:8000/openapi.json | Esquema para Postman/Insomnia |

**Orden de prueba:** `GET /health` → `POST /ingest` (si no hay datos) → `GET /search?q=Gonzalez`

**Producción:** desactiva Swagger con `VZ_SEARCH_ENABLE_DOCS=false`

## Configuración (5 minutos)

### 1. API key gratis de Gemini

1. Entra a [Google AI Studio](https://aistudio.google.com/apikey)
2. Crea una API key
3. Copia `.env.example` → `.env` y pega la key:

```env
VZ_SEARCH_GEMINI_API_KEY=tu_key_aqui
VZ_SEARCH_INGEST_MODE=ai
VZ_SEARCH_STORAGE=memory
```

### 2. Descargar documentos

Descarga la carpeta de Google Drive y descomprime en `./data/` (mantén subcarpetas por hospital).

### 3. Instalar y arrancar

```powershell
cd C:\Users\casa\Documents\vz-search
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Una pasada de IA (puede tardar según cantidad de PDFs)
python scripts\ingest.py

# API lista para buscar
python run.py
```

O todo desde la API:

```powershell
python run.py
# Luego POST http://127.0.0.1:8000/api/v1/ingest
```

Docs: http://127.0.0.1:8000/docs

## Endpoints

```http
GET  /api/v1/health
POST /api/v1/ingest     ← una pasada IA, carga memoria volátil
GET  /api/v1/search?q=Gonzalez&hospital=Perez&state=Miranda
```

### Ejemplo respuesta búsqueda

```json
{
  "total": 1,
  "cached": false,
  "results": [{
    "full_name": "María González",
    "hospital": "HOSPITAL PEREZ CARREÑO",
    "state": "Miranda",
    "cedula": "V-12345678",
    "content": "María González | Cédula: V-12345678 | Condición: estable",
    "score": 98
  }]
}
```

## Arquitectura hexagonal

```
domain/ports/DocumentAnalyzerPort  ← contrato IA (una pasada)
infrastructure/ai/GeminiDocumentAnalyzer  ← lee PDF/imagen
infrastructure/persistence/InMemoryRecordRepository  ← RAM volátil
application/SearchUseCase  ← búsqueda sin IA
adapters/api/  ← REST FastAPI
```

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `VZ_SEARCH_GEMINI_API_KEY` | — | **Requerida** para PDFs escaneados |
| `VZ_SEARCH_INGEST_MODE` | `ai` | `ai` o `text` (solo PDFs con texto) |
| `VZ_SEARCH_STORAGE` | `memory` | Memoria volátil (se pierde al reiniciar) |
| `VZ_SEARCH_AUTO_INGEST_ON_STARTUP` | `false` | Si `true`, ingiere al arrancar |
| `VZ_SEARCH_MAX_PDF_PAGES` | `15` | Máx. páginas por PDF por llamada IA |
| `VZ_SEARCH_GEMINI_MODEL` | `gemini-2.0-flash` | Modelo vision gratis |

## Notas importantes

- **Memoria volátil:** al reiniciar el servidor hay que volver a hacer `POST /ingest` (una pasada IA).
- **Costo:** Gemini Flash tiene cuota gratis generosa; cada archivo = 1 llamada IA.
- **Sin API key:** modo `text` solo funciona con PDFs que tienen texto seleccionable, no escaneados.

## Alternativa sin código: NotebookLM

Si no quieres instalar nada, sube los PDFs a [NotebookLM](https://notebooklm.google.com) y pregunta por nombre.  
Esta API es mejor cuando necesitas un buscador propio compartible con familiares.
