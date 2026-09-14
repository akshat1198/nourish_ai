FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/opt/models

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding weights into the image. Without this the first request that
# touches pgvector retrieval downloads ~90 MB from HuggingFace onto the host's
# ephemeral disk -- on every cold start, since the filesystem does not survive a
# restart. Build-time failure here is deliberate: shipping an image that has to
# reach HuggingFace to answer a recipe query is the bug.
RUN python -c "from fastembed import TextEmbedding; \
TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2').embed(['warm'])"

# Copy application code
COPY app ./app
# Canonical ingredient properties (diet/allergen/nutrition) live here, read at
# runtime by app/services/derivation.py for post-swap re-validation (7.3).
COPY seed_data ./seed_data
# Migrations ship with the image so the container can bring its own schema up
# to date. Without these the image cannot migrate at all, and a deploy whose
# models expect new columns just 500s on every request that touches them.
COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8000

# Migrate before serving. A failed migration must stop the boot rather than
# serve traffic against a schema the code does not match — the health check
# then fails and the platform keeps the previous release.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
