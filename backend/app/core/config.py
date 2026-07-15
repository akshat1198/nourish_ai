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
    PROMPT_VERSION: str = "v1"  # logged per run; real versioning in 3.4
    REPAIR_MAX_ATTEMPTS: int = 2  # LLM-05: repair turns before deterministic fallback

    # Edamam live web search (Stage 6.5). Supplemental discovery/link-out only —
    # results are NEVER stored or fed into pantry-matching/ranking (TOS). Feature
    # is off (fail-open) unless BOTH id and key are set.
    EDAMAM_APP_ID: str = ""
    EDAMAM_APP_KEY: str = ""

    # Ranking weights (RETR-03). Bump RANKING_VERSION on any change so the
    # recommendation cache (RETR-04) invalidates.
    RANKING_VERSION: str = "v2"  # v2: soft dislike penalty
    RANK_W_COVERAGE: float = 0.6  # reward covering essential ingredients
    RANK_W_MISSING: float = 0.3  # penalize missing ingredients
    RANK_W_TIME: float = 0.1  # reward fitting the time budget
    RANK_TIME_REFERENCE: int = 60  # minutes; time_fit = 1 - time/reference (clamped)
    # Soft demotion for a disliked ingredient: large enough to dominate the base
    # score span (~[-0.3, 0.7]) so disliked recipes sink beneath every clean one,
    # but they stay in the list — chosen only if nothing clean fits.
    RANK_W_DISLIKE: float = 1.0

    # Recommendation cache (RETR-04)
    CACHE_TTL_SECONDS: int = 300

    # Low-confidence fallback (RETR-05): if the top recipe covers fewer than
    # this fraction of its essential ingredients, switch to a fallback mode.
    FALLBACK_COVERAGE_THRESHOLD: float = 0.34

    # Orchestrator checkpointing (AGENT-04): memory | postgres
    CHECKPOINT_BACKEND: str = "memory"

    # Auth (Stage 5). "disabled" (default) keeps the API open and honours an
    # X-User-Key header (dev/test); "jwt" verifies an HS256 bearer minted by the
    # Next.js Auth.js layer with AUTH_SHARED_SECRET.
    AUTH_MODE: str = "disabled"  # disabled | jwt
    AUTH_SHARED_SECRET: str = ""
    AUTH_JWT_ISS: str = "nourish-web"
    AUTH_JWT_AUD: str = "nourish-api"
    # Comma-separated browser origins allowed by CORS (Stage 5 frontend).
    CORS_ORIGINS: str = "http://localhost:3000"

    # Nutrition-goal thresholds (Stage 5) — deterministic per-serving cutoffs
    # over recipes.nutrition. A recipe passes a goal if it meets the cutoff.
    NUTRI_HIGH_PROTEIN_G: float = 25.0  # protein_g >=
    NUTRI_LOW_CALORIE_KCAL: float = 400.0  # calories <=
    NUTRI_LOW_FAT_G: float = 10.0  # fat_g <=
    NUTRI_LOW_CARB_G: float = 20.0  # carbs_g <=

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
