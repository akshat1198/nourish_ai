from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://pantry:pantrypw@localhost:5432/pantrydb"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Ranking weights (RETR-03). Bump RANKING_VERSION on any change so the
    # recommendation cache (RETR-04) invalidates.
    RANKING_VERSION: str = "v1"
    RANK_W_COVERAGE: float = 0.6  # reward covering essential ingredients
    RANK_W_MISSING: float = 0.3  # penalize missing ingredients
    RANK_W_TIME: float = 0.1  # reward fitting the time budget
    RANK_TIME_REFERENCE: int = 60  # minutes; time_fit = 1 - time/reference (clamped)

    # Recommendation cache (RETR-04)
    CACHE_TTL_SECONDS: int = 300


settings = Settings()
