# NourishAI

AI recipe-recommendation platform: pantry input → ranked, diet/allergen-safe recipes + substitutions + shopping lists + meal plans. FastAPI backend, Next.js frontend, agentic tool-calling layer on top of hybrid retrieval.

For the full stage-by-stage build history and architectural decision log, see `PLAN.md` (gitignored, local-only — read it if you need historical "why" beyond what's below). `README.md` is the user-facing description of what's shipped.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2 + Postgres 16/pgvector + Redis, via `docker compose`. Alembic migrations under `backend/alembic/versions/`.
- **Frontend**: Next.js 15 (App Router) + React 19 + Tailwind v4 + TanStack Query 5 + Auth.js (NextAuth v5, Google OAuth, HS256 bearer to the backend).
- **LLM**: Anthropic Claude behind `backend/app/llm/client.py` — fails open (returns None/degraded, never throws) when no API key is set.
- **Agent**: two engines share one trace format — a raw Anthropic tool-calling loop (`backend/app/agent/`) and a LangGraph supervisor (`backend/app/orchestrator/`) — plus an MCP server (`backend/app/mcp_server.py`) exposing the same tools.

## Commands

```
make setup          # ./dev-setup.sh — venv, docker services, migrations, API server
make up / down       # docker compose up/down
make api             # run FastAPI locally with --reload (services must be up)
make migrate         # alembic upgrade head
make test            # backend pytest
make psql / redis    # shells into the postgres/redis containers
make mcp / mcp-verify

cd frontend && npm run dev / build / lint
```

## Architecture (backend/app)

```
api/          route handlers, one file per resource
services/     business logic — retrieval, ranking, personalization, fallback, etc.
models/       SQLAlchemy ORM
schemas/      Pydantic request/response shapes
agent/        raw tool-calling loop, prompts, validator, tracing
orchestrator/ LangGraph supervisor + checkpointing
evals/        offline eval harnesses (retrieval, agent, fallback) — run manually, not in CI
```

Recommend flow: SQL ingredient-match + pgvector KNN candidates, **each arm filtered before its LIMIT** → RRF fusion → `_passes_filters` re-asserts the hard tier post-fusion → ranking → fallback. Personalization can only ever reorder an already-filtered set — it must never be able to surface a diet/allergen violation; if you touch `ranking.py` or `personalization.py`, preserve that ordering.

**Filters come in three tiers** (`retrieval.hard_clauses` / `soft_clauses`); the tier decides the mechanism, and collapsing them is how the "no results" and "wrong cuisine" bugs happened:

| Tier | Filters | Mechanism |
|---|---|---|
| Safety | `diet`, `exclude_allergens` | Hard SQL exclude. Never counted, relaxed, or ranked. |
| Cuisine | `cuisines` | Hard on the primary pass. A shortfall appends other cuisines *below a divider* with `cuisine_matched=False` — never blended in, never silently substituted. |
| Preference | `meal_type` | Binary ranking dimensions. Retrieval prefers them, then tops up from the unfiltered pool; a miss demotes, never excludes. |
| Preference | `nutrition_goals` | **Graded, not gated.** Never counted into `filters_matched` — ranked by degree via `nutrition_fit` (protein up; calories/fat/carbs down, each normalized by its threshold). Asking for high protein returns the highest protein available even when nothing clears 25 g, which no vegetarian Thai recipe in the corpus does. Strict callers (`soften=False`) keep exact threshold semantics. |

Ordering is **strict/lexicographic**, not a score blend (`ranking.order_key`): `cuisine_matched` → not-disliked → `pantry_complete` → `filters_matched` → score. Cuisine sits above pantry-completeness on purpose — a fully-stocked Indian recipe must not outrank a partially-stocked Italian one when Italian was requested.

**Generation fills corpus gaps, it doesn't replace the corpus** (`services/generation.py`). When a request has fewer than `GENERATION_MIN_RESULTS` in-cuisine matches, Claude writes recipes for that exact filter payload; they're validated, embedded, and persisted with `source="generated"`, so the corpus grows toward real demand and the next identical request is a DB hit. Non-negotiables if you touch it:

- **Nothing the model asserts is trusted.** Diet and allergen labels are re-derived from the generated ingredient list by `classify_and_derive`; a recipe whose *derived* labels contradict the request is discarded, never repaired. The **cuisine is taken from the request's taxonomy id, not the model's word** — asked for `asian/korean` it answers `cuisine="korean"`, and storing that makes the recipe unmatchable by the filter that asked for it.
- **A proposed new ingredient is range-checked before insert** (`_ingredient_is_plausible`): category/unit/allergens must be on-vocab, macros must be physically possible *and* reconcile with the stated calories. A hallucinated `per_100g` becomes the basis for the nutrition of every recipe that later uses it.
- **Fails open.** `generate_recipes` never raises; any error degrades to whatever retrieval found. Every run writes a `GenerationEvent` with its violations.
- Generation needs a longer timeout than the rest of the LLM surface (`GENERATION_TIMEOUT_SECONDS`); `LLM_TIMEOUT_SECONDS` is sized for short prompts and aborts a multi-recipe write mid-flight.

**Ingredient properties live on the `ingredients` table**, not in `seed_data/ingredients.json` — the seed file is only the bootstrap for a fresh install and the no-session fallback. That move is what lets vocabulary be added at runtime (a generated recipe needing fish sauce) and have working nutrition immediately, so `load_props(session)` is deliberately uncached. Every writer builds rows through `derivation.ingredient_columns()`; adding a property means adding it there, or seeded rows get NULLs that read as "not vegan, no nutrition".

**Nutrition is 100% derived, never sourced** — no importer supplies it, so every number comes from `derivation.py` summing matched ingredient grams. That makes `measure_to_grams` the single point of failure for all four nutrition goals: it once read "3 chicken breast" as 3 g (the `grams_per_unit` for anything stored in grams is 1), putting whole cuisines under the protein threshold. Ingredients now carry `grams_per_piece` — what one bare unit weighs — and the parser handles oz/lb, fractions, and gram weights written without a space ("25g"). If you touch it, re-run `scripts/rederive_nutrition.py` and check the macros still reconcile with the calorie totals.

Ingredient matches are **category-weighted** (`RANK_CAT_WEIGHTS`): a matched protein counts ~5x a matched spice. Counting them equally biased results toward spice-dense cuisines — Indian recipes average 61% spice/pantry/herb vs ~42% elsewhere, so any stocked spice rack scored high coverage and low missing on them regardless of the actual protein. Don't revert to raw counts.

## Known sharp edges

- **Two separate Redis caches in the recommend path**, easy to bust only one and ship a bug: the taste-vector cache (`taste:{user}:{RANKING_VERSION}`) and the response cache (`rec:{hash}:{RANKING_VERSION}`). Busting the taste-vector cache alone does NOT make personalization changes show up immediately — the response cache will still serve a stale full response for an identical repeated request. Current fix: response caching (read + write) is skipped entirely whenever a request is personalized (`tvec is not None`); `X-Cache` response header is `hit` / `miss` / `skip-personalized`.
- **A/B variant assignment must be deterministic across requests**: `assign_variant()` uses `hashlib.sha256(f"{experiment}:{session_id}")`, never Python's built-in `hash()` (salted per-process, would reassign on every restart). The `control` variant must never personalize regardless of the `PERSONALIZATION_ENABLED` flag — don't let a "no vector supplied, look one up" fallback path silently re-personalize a control user when `tvec` is deliberately `None`.
- **Docker deployment**: the `nourishai-api` container has no source mount. Code-only changes: `docker compose cp backend/<file> backend:/app/<file>` + `docker compose restart backend`. If `docker-compose.yml` itself changes (new env var, etc.), `restart` won't pick it up — you need `docker compose up -d backend`, and if the image hasn't been rebuilt this session, that silently reverts the container to the last-built image, discarding every `cp`-only deploy since. Always `docker compose build backend` before `up -d` when compose config changed, and verify routes are still live afterward.
- **Diet-implied allergens**: Vegan implies dairy/eggs/fish/shellfish excluded; vegetarian (non-vegan) implies only fish/shellfish; gluten-free implies gluten. Grounded in `services/derivation.py::classify_and_derive` — don't hardcode this mapping a second place, reuse `dietImpliedAllergens()` (frontend) / the derivation logic (backend).
- **`archana_dataset.csv`** (repo root, gitignored) is real source data still used by `backend/scripts/ingest/archanas.py`, `analyze.py`, and `verify_backfill.py` — don't treat it as stale cruft.

## Conventions

- No emoji in code, comments, or CLI output. No "AI-generated" tells in comments — no "Stage N" / "WS-N" / ticket-ID scaffolding (`RETR-05`, `AGENT-12`, etc.) referencing internal build phases; write comments as a human engineer would, explaining the why for the current code, not the history of how it got built.
- Commit messages: no attribution trailer, explain why not what, created fresh (not amended) per commit.
- Comment only on non-obvious WHY (hidden constraint, workaround, invariant) — not on WHAT the code does.
- Watch the Github CI run kickoff after the commit and ensure it builds successfully. Fix any issues that arise.
