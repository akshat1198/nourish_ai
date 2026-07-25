from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://pantry:pantrypw@localhost:5432/pantrydb"
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM adapter. Feature is disabled if ANTHROPIC_API_KEY is unset
    # — the deterministic path still works (fail-open).
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_MAIN: str = "claude-sonnet-5"  # workhorse agent model
    LLM_MODEL_FAST: str = "claude-haiku-4-5"  # cheap/fast (pantry-text parsing)
    LLM_MODEL_JUDGE: str = "claude-opus-4-8"  # offline eval judge only
    LLM_TIMEOUT_SECONDS: float = 20.0
    PROMPT_VERSION: str = "v1"  # logged per run; real versioning tracked separately
    REPAIR_MAX_ATTEMPTS: int = 2  # repair turns before deterministic fallback

    # Ranking weights. Bump RANKING_VERSION on any change so the
    # recommendation cache invalidates.
    RANKING_VERSION: str = "v4"  # v4: category-weighted matches + tiered filter ordering
    RANK_W_COVERAGE: float = 0.6  # reward covering essential ingredients
    RANK_W_MISSING: float = 0.3  # penalize missing ingredients
    RANK_W_TIME: float = 0.1  # reward fitting the time budget
    RANK_TIME_REFERENCE: int = 60  # minutes; time_fit = 1 - time/reference (clamped)
    # Per-category match weight. Counting every ingredient equally biased results
    # toward spice-dense cuisines: Indian recipes average 61% spice/pantry/herb vs
    # ~42% elsewhere, so any stocked spice rack scored high coverage AND low
    # missing on them before the protein or vegetable was ever considered.
    # Unlisted categories fall back to RANK_CAT_WEIGHT_DEFAULT.
    RANK_CAT_WEIGHTS: dict[str, float] = Field(
        default_factory=lambda: {
            "protein": 1.0,
            "vegetable": 1.0,
            "grain": 0.9,
            "starch": 0.9,
            "dairy": 0.8,
            "fruit": 0.8,
            "sauce": 0.6,
            "herb": 0.3,
            "spice": 0.2,
            "pantry": 0.2,
        }
    )
    RANK_CAT_WEIGHT_DEFAULT: float = 0.8
    # An ingredient at/above this weight is "substantive" — a recipe missing none
    # of them counts as cookable from the pantry alone (missing cumin doesn't
    # disqualify a recipe; missing the chicken does).
    RANK_SUBSTANTIVE_MIN_WEIGHT: float = 0.5
    # Soft demotion for a disliked ingredient: large enough to dominate the base
    # score span (~[-0.3, 0.7]) so disliked recipes sink beneath every clean one,
    # but they stay in the list — chosen only if nothing clean fits.
    RANK_W_DISLIKE: float = 1.0

    # Learned personalization. The taste term is applied AFTER hard
    # filters in ranking.py — it can only reorder the already-safe set.
    PERSONALIZATION_ENABLED: bool = True
    RANK_W_TASTE: float = 0.15  # small — base score span is ~[-0.3, 0.7]
    TASTE_NEG_WEIGHT: float = 0.5
    TASTE_CACHE_TTL: int = 600

    # Online A/B. "control" never personalizes (via the personalization gate);
    # any other variant follows PERSONALIZATION_ENABLED as usual.
    EXPERIMENT_NAME: str = "ranking_ab"
    EXPERIMENT_VARIANTS: str = "control,personalized"

    @property
    def experiment_variants_list(self) -> list[str]:
        return [v.strip() for v in self.EXPERIMENT_VARIANTS.split(",") if v.strip()]

    # Recommendation cache
    CACHE_TTL_SECONDS: int = 300

    # Low-confidence fallback: if the top recipe covers fewer than
    # this fraction of its essential ingredients, switch to a fallback mode.
    FALLBACK_COVERAGE_THRESHOLD: float = 0.34

    # Orchestrator checkpointing: memory | postgres
    CHECKPOINT_BACKEND: str = "memory"

    # Auth. "disabled" (default) keeps the API open and honours an
    # X-User-Key header (dev/test); "jwt" verifies an HS256 bearer minted by the
    # Next.js Auth.js layer with AUTH_SHARED_SECRET.
    AUTH_MODE: str = "disabled"  # disabled | jwt
    AUTH_SHARED_SECRET: str = ""
    AUTH_JWT_ISS: str = "nourish-web"
    AUTH_JWT_AUD: str = "nourish-api"
    # Comma-separated browser origins allowed by CORS.
    CORS_ORIGINS: str = "http://localhost:3000"

    # Nutrition-goal thresholds — deterministic per-serving cutoffs
    # over recipes.nutrition. A recipe passes a goal if it meets the cutoff.
    NUTRI_HIGH_PROTEIN_G: float = 25.0  # protein_g >=
    NUTRI_LOW_CALORIE_KCAL: float = 400.0  # calories <=
    NUTRI_LOW_FAT_G: float = 10.0  # fat_g <=
    NUTRI_LOW_CARB_G: float = 20.0  # carbs_g <=

    # Observability admin gate. Fail-closed: an unset token locks
    # the endpoint even if a caller somehow supplies a matching empty header.
    ADMIN_TOKEN: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()


def category_weight(category: str | None) -> float:
    """Ranking weight for one ingredient category."""
    if not category:
        return settings.RANK_CAT_WEIGHT_DEFAULT
    return settings.RANK_CAT_WEIGHTS.get(category, settings.RANK_CAT_WEIGHT_DEFAULT)


# Human-readable cutoff labels for the nutrition goals (single source of truth,
# used by the recommend explanation and the /v1/config endpoint the UI reads).
def nutrition_goal_label(goal: str) -> str:
    return {
        "high_protein": f"high-protein (≥{settings.NUTRI_HIGH_PROTEIN_G:g} g)",
        "low_calorie": f"low-calorie (≤{settings.NUTRI_LOW_CALORIE_KCAL:g} kcal)",
        "low_fat": f"low-fat (≤{settings.NUTRI_LOW_FAT_G:g} g)",
        "low_carb": f"low-carb (≤{settings.NUTRI_LOW_CARB_G:g} g)",
    }.get(goal, goal)
