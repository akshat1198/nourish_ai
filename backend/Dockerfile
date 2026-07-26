FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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
