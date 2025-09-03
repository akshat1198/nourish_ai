from fastapi import FastAPI
from sqlalchemy import text
from app.db import engine
from app.cache import redis_client

app = FastAPI()

@app.get("/health")
def health():
    ok_db = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        ok_db = False
        print(f"Database connection error: {str(e)}")

    ok_redis = redis_client.ping() if redis_client else False
    return {"db": ok_db, "redis": ok_redis}
