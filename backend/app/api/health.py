import json
import logging
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import text
from app.db import engine
from app.cache import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


def get_app_version():
    """Get version from package.json if available, otherwise use env var."""
    try:
        # Try to read from frontend package.json
        package_json_path = (
            Path(__file__).parent.parent.parent.parent / "frontend" / "package.json"
        )
        if package_json_path.exists():
            with open(package_json_path) as f:
                package_data = json.load(f)
                return package_data.get("version", "unknown")
    except Exception:
        pass

    # Fallback to environment variable
    return os.getenv("APP_VERSION", "dev")


def get_commit_hash():
    """Get current git commit hash dynamically."""
    try:
        # Try to get current commit hash from git
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,  # Go to repo root
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    # Fallback to environment variable
    return os.getenv("COMMIT_HASH", "unknown")


@router.get("/health")
def health():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
    - status: "ok" if all services healthy, "error" if any issues
    - db: boolean indicating database connectivity
    - redis: boolean indicating Redis connectivity
    - version: app version and commit hash for deployment tracking
    """
    # Check DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok_db = True
    except Exception as e:
        ok_db = False
        logger.warning("health: database unreachable: %s", e)

    # Check Redis
    try:
        ok_redis = redis_client.ping() if redis_client else False
    except Exception as e:
        ok_redis = False
        # Log it. A bare `redis: false` gives no way to tell a wrong scheme from
        # a wrong host from bad credentials, and the cache fails open, so the
        # only symptom is every request quietly missing the cache forever.
        logger.warning("health: redis unreachable (%s): %s", type(e).__name__, e)

    # Top-level status for monitoring tools
    status = ok_db and ok_redis

    return {
        "status": "ok" if status else "error",
        "db": ok_db,
        "redis": ok_redis,
        "version": {"app": get_app_version(), "commit": get_commit_hash()},
    }
