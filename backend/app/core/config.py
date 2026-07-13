from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://pantry:pantrypw@localhost:5432/pantrydb"
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM adapter (Stage 2.3). Feature is disabled if ANTHROPIC_API_KEY is unset
    # — the deterministic path still works (fail-open).
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_MAIN: str = "claude-sonnet-5"  # workhorse (Stage 3 agent)
    LLM_MODEL_FAST: str = "claude-haiku-4-5"  # cheap/fast (pantry-text parsing)
    LLM_MODEL_JUDGE: str = "claude-opus-4-8"  # offline eval judge only
    LLM_TIMEOUT_SECONDS: float = 20.0

    # Ranking weights (RETR-03). Bump RANKING_VERSION on any change so the
    # recommendation cache (RETR-04) invalidates.
    RANKING_VERSION: str = "v1"
    RANK_W_COVERAGE: float = 0.6  # reward covering essential ingredients
    RANK_W_MISSING: float = 0.3  # penalize missing ingredients
    RANK_W_TIME: float = 0.1  # reward fitting the time budget
    RANK_TIME_REFERENCE: int = 60  # minutes; time_fit = 1 - time/reference (clamped)

    # Recommendation cache (RETR-04)
    CACHE_TTL_SECONDS: int = 300

    # Low-confidence fallback (RETR-05): if the top recipe covers fewer than
    # this fraction of its essential ingredients, switch to a fallback mode.
    FALLBACK_COVERAGE_THRESHOLD: float = 0.34


settings = Settings()
