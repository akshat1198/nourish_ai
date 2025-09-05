import os
import subprocess
import json
from pathlib import Path
from fastapi import FastAPI
from sqlalchemy import text
from app.db import engine
from app.cache import redis_client

def get_app_version():
    """Get version from package.json if available, otherwise use env var."""
    try:
        # Try to read from frontend package.json
        package_json_path = Path(__file__).parent.parent.parent / "frontend" / "package.json"
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
            cwd=Path(__file__).parent.parent.parent  # Go to repo root
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Fallback to environment variable
    return os.getenv("COMMIT_HASH", "unknown")

# Get version info dynamically
APP_VERSION = get_app_version()
COMMIT_HASH = get_commit_hash()

app = FastAPI()

@app.get("/health")
def health():
    # Check DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok_db = True
    except Exception as e:
        ok_db = False
        print(f"Database connection error: {str(e)}")

    # Check Redis
    try:
        ok_redis = redis_client.ping() if redis_client else False
    except Exception:
        ok_redis = False

    # Top-level status for monitoring tools
    status = ok_db and ok_redis
    
    return {
        "status": "ok" if status else "error",
        "db": ok_db,
        "redis": ok_redis,
        "version": {
            "app": APP_VERSION,
            "commit": COMMIT_HASH
        }
    }
