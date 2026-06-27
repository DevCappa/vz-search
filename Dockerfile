FROM python:3.11-slim

WORKDIR /app

COPY requirements-railway.txt .
RUN pip install --no-cache-dir -r requirements-railway.txt

COPY src/ ./src/
COPY run.py pyproject.toml ./

ENV PYTHONPATH=/app/src
ENV VZ_SEARCH_API_HOST=0.0.0.0
ENV VZ_SEARCH_STORAGE=sqlite
ENV VZ_SEARCH_INGEST_MODE=search-only
ENV VZ_SEARCH_ENABLE_DOCS=true

EXPOSE 8000

CMD ["sh", "-c", "uvicorn vz_search.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
