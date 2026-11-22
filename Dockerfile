FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    STORAGE_DIR=/app/storage \
    FAISS_INDEX_PATH=/app/storage/faiss_index \
    DOCUMENTS_DB_PATH=/app/storage/documents.json \
    EMBEDDING_CACHE_DIR=/app/models \
    GOOGLE_OAUTH_INTERACTIVE=false

WORKDIR /app

# All dependencies ship as binary wheels, so no compiler toolchain is needed.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image: no download on every cold start.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='${EMBEDDING_MODEL}', cache_dir='/app/models')"

# .dockerignore keeps .env, credentials, tokens and local storage out of the image.
COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/storage /app/secrets \
    && chown -R appuser:appuser /app/storage /app/secrets /app/models
USER appuser

EXPOSE 8000

# Fails on any non-2xx response, not just on connection errors.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=5)"

# Cloud Run and Render inject $PORT; default 8000 for local Docker.
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
