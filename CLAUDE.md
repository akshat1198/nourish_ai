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
| Preference | `nutrition_goals` | **Graded, not gated — but capped.** Never counted into `filters_matched` — ranked by degree via `nutrition_fit` (protein up; calories/fat/carbs down, each normalized by its threshold, then clamped to `NUTRI_FIT_CAP` multiples of it). Asking for high protein returns the highest protein available even when nothing clears 25 g, which no vegetarian Thai recipe in the corpus does. Strict callers (`soften=False`) keep exact threshold semantics. |

Ordering is **strict/lexicographic**, not a score blend (`ranking.order_key`): `cuisine_matched` → not-disliked → `filters_matched` → `nutrition_fit` → `pantry_complete` → score. Two deliberate placements: cuisine above everything, so a fully-stocked Indian recipe can't outrank a partially-stocked Italian one when Italian was asked for; and the filters above pantry fit, so asking for high protein can't put a low-protein recipe on top just because nothing is missing from it.

**Generation fills corpus gaps, it doesn't replace the corpus** (`services/generation.py`). When a request has fewer than `GENERATION_MIN_RESULTS` in-cuisine matches, Claude writes recipes for that exact filter payload; they're validated, embedded, and persisted with `source="generated"`, so the corpus grows toward real demand and the next identical request is a DB hit. Non-negotiables if you touch it:

- **Nothing the model asserts is trusted.** Diet and allergen labels are re-derived from the generated ingredient list by `classify_and_derive`; a recipe whose *derived* labels contradict the request is discarded, never repaired. The **cuisine is taken from the request's taxonomy id, not the model's word** — asked for `asian/korean` it answers `cuisine="korean"`, and storing that makes the recipe unmatchable by the filter that asked for it.
- **A proposed new ingredient is range-checked before insert** (`_ingredient_is_plausible`): category/unit/allergens must be on-vocab, macros must be physically possible *and* reconcile with the stated calories. A hallucinated `per_100g` becomes the basis for the nutrition of every recipe that later uses it.
- **Fails open.** `generate_recipes` never raises; any error degrades to whatever retrieval found. Every run writes a `GenerationEvent` with its violations.
- Generation needs a longer timeout than the rest of the LLM surface (`GENERATION_TIMEOUT_SECONDS`); `LLM_TIMEOUT_SECONDS` is sized for short prompts and aborts a multi-recipe write mid-flight.

**Ingredient properties live on the `ingredients` table**, not in `seed_data/ingredients.json` — the seed file is only the bootstrap for a fresh install and the no-session fallback. That move is what lets vocabulary be added at runtime (a generated recipe needing fish sauce) and have working nutrition immediately, so `load_props(session)` is deliberately uncached. Every writer builds rows through `derivation.ingredient_columns()`; adding a property means adding it there, or seeded rows get NULLs that read as "not vegan, no nutrition".

**Nutrition is never sourced — it is derived, and only estimated where deriving fails.** No importer supplies it. `recipes.nutrition_source` says which happened: `derived` (the norm, ~94% — `derivation.py` summing matched ingredient grams), `llm` (~5%), or `none`. That makes `measure_to_grams` the single point of failure for all four nutrition goals: it once read "3 chicken breast" as 3 g (the `grams_per_unit` for anything stored in grams is 1), putting whole cuisines under the protein threshold. Ingredients now carry `grams_per_piece` — what one bare unit weighs — and the parser handles oz/lb, fractions, and gram weights written without a space ("25g"). If you touch it, re-run `scripts/rederive_nutrition.py` (`--stats` prints the per-serving distribution; compare it before and after).

A line with **neither a quantity nor a unit means "to taste"** and resolves to a category-scaled trace, not one whole piece. Ingestion strips the qualifier (`normalize.py` splits on `" - "`), so absence is the only signal left; reading it as one piece put 6 g of salt and 15 g of oil into 12% of all ingredient rows. `_parse_qty` returns `None` rather than defaulting to 1 so the two cases stay distinguishable — do not reinstate that default.

**Derived nutrition is written only if it is plausible** (`derivation.nutrition_usable`, ceilings in `config.py` sized from the corpus p99). An implausible sum is worse than none: ranking orders by macro, so the worst-parsed rows surfaced first. Rows that fail are stored empty and picked up by `scripts/estimate_nutrition_llm.py`, which asks the model for per-serving macros and **subjects them to the identical ceilings plus a 4/4/9 reconciliation** — an estimate that cleared a looser bar would just launder a bad number past the gate. Fails open; a rejected estimate leaves the recipe with no nutrition rather than a guess. That backfill is offline on purpose: retrieval filters and orders on `recipes.nutrition` **in SQL during candidate selection**, so a lazily-computed value could never surface a recipe the filter had already dropped. Note the reconciliation is near-useless against *derived* values (calories and macros are summed from the same grams and agree by construction — 21 of 7,533 rows fail); it earns its keep only on independently-generated numbers.

Ingredient matches are **category-weighted** (`RANK_CAT_WEIGHTS`): a matched protein counts ~5x a matched spice. Counting them equally biased results toward spice-dense cuisines — Indian recipes average 61% spice/pantry/herb vs ~42% elsewhere, so any stocked spice rack scored high coverage and low missing on them regardless of the actual protein. Don't revert to raw counts.

## Known sharp edges

- **Two separate Redis caches in the recommend path**, easy to bust only one and ship a bug: the taste-vector cache (`taste:{user}:{RANKING_VERSION}`) and the response cache (`rec:{hash}:{RANKING_VERSION}`). Busting the taste-vector cache alone does NOT make personalization changes show up immediately — the response cache will still serve a stale full response for an identical repeated request. Current fix: response caching (read + write) is skipped entirely whenever a request is personalized (`tvec is not None`); `X-Cache` response header is `hit` / `miss` / `skip-personalized`.
- **A/B variant assignment must be deterministic across requests**: `assign_variant()` uses `hashlib.sha256(f"{experiment}:{session_id}")`, never Python's built-in `hash()` (salted per-process, would reassign on every restart). The `control` variant must never personalize regardless of the `PERSONALIZATION_ENABLED` flag — don't let a "no vector supplied, look one up" fallback path silently re-personalize a control user when `tvec` is deliberately `None`.
- **Docker deployment**: the `nourishai-api` container has no source mount. Code-only changes: `docker compose cp backend/<file> backend:/app/<file>` + `docker compose restart backend`. If `docker-compose.yml` itself changes (new env var, etc.), `restart` won't pick it up — you need `docker compose up -d backend`, and if the image hasn't been rebuilt this session, that silently reverts the container to the last-built image, discarding every `cp`-only deploy since. Always `docker compose build backend` before `up -d` when compose config changed, and verify routes are still live afterward.
- **Diet-implied allergens**: Vegan implies dairy/eggs/fish/shellfish excluded; vegetarian (non-vegan) implies only fish/shellfish; gluten-free implies gluten. Grounded in `services/derivation.py::classify_and_derive` — don't hardcode this mapping a second place, reuse `dietImpliedAllergens()` (frontend) / the derivation logic (backend).
- **`archana_dataset.csv`** (repo root, gitignored) is real source data still used by `backend/scripts/ingest/archanas.py`, `analyze.py`, and `verify_backfill.py` — don't treat it as stale cruft.
- **The nutrition plausibility gate exists twice**: `derivation.nutrition_usable` in Python and a mirror inside `retrieval.soft_clauses` in SQL. They must agree, or a recipe is filtered one way during retrieval and judged another way in ranking. Both now build from `derivation.plausible_bounds()` and a test asserts they select the same recipes over the real corpus — add a bound there, not in either consumer. Note the SQL side drops a row whose macro key is missing (NULL comparison) where Python reads it as 0, so partial nutrition dicts would diverge; nothing writes those today.
- **Changing nutrition values or ranking means bumping `RANKING_VERSION`.** It keys both Redis caches, so without the bump an identical repeat request keeps serving the pre-change ranking and the fix looks unshipped. Verify with the `X-Cache` header: the first post-deploy request for a previously-cached payload must be `miss`.
- **Source `servings` is not reliable** and is the largest remaining error source. Archana's claims 2 servings for 750 g of chicken; TheMealDB hardcodes 4 for all ~700 of its rows. On the LLM backfill the model read a different serving count on 157 of 389 recipes. Related and unfixed: generic source names are aliased to specific canonicals (`chicken` → `chicken breast`), so a whole bone-in bird is priced at breast-meat macros. Fixing that needs re-reading source data — `backfill_ingredients.py --relabel` already overwrote the display names, so the raw source name is gone from the DB — and it changes pantry matching too, so it is not a nutrition-only change.

## Conventions

- No emoji in code, comments, or CLI output. No "AI-generated" tells in comments — no "Stage N" / "WS-N" / ticket-ID scaffolding (`RETR-05`, `AGENT-12`, etc.) referencing internal build phases; write comments as a human engineer would, explaining the why for the current code, not the history of how it got built.
- Commit messages: no attribution trailer, explain why not what, created fresh (not amended) per commit.
- Comment only on non-obvious WHY (hidden constraint, workaround, invariant) — not on WHAT the code does.
- Watch the Github CI run kickoff after the commit and ensure it builds successfully. Fix any issues that arise.
- After successful github build, ensure successful deployment to Vercel website