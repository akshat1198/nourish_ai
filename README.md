# NourishAI

NourishAI turns what's in your pantry into recipes you can actually cook tonight. Tell it your ingredients and tonight's mood — cuisine, meal, diet, allergens, time, nutrition goals — through a guided, one-filter-per-page flow, and it returns ranked, diet- and allergen-safe recipes drawn from a ~7,600-recipe corpus, with smart substitutions, an adaptive method, serving-size scaling, and a shopping list for anything you're missing. Save recipes, group them into meal plans with a combined shopping list, and the more you cook, save, and dismiss, the better it gets at ranking for your taste.

It's a full-stack, working application built to demonstrate **production-oriented LLM patterns**: hybrid retrieval-augmented generation, deterministic-first validation, structured model outputs, tool/function calling, a single-agent loop, and a multi-agent LangGraph orchestrator exposed over MCP.

## Table of Contents
- [What It Does](#what-it-does)
- [Features](#features)
- [How It Works](#how-it-works)
- [AI & LLM Design](#ai--llm-design)
- [Technology Stack](#technology-stack)
- [API](#api)
- [Data & Ingestion](#data--ingestion)
- [Local Development](#local-development)
- [Testing & CI](#testing--ci)
- [Repository Structure](#repository-structure)
- [Project Status](#project-status)
- [License](#license)

## What It Does

1. **Stock a pantry** — add ingredients (with autocomplete over a canonical vocabulary and aliases) plus everyday staples, or just describe what you have in a sentence ("half a bag of spinach, a couple eggs") and let a fast LLM pass parse it. Saved per user. Generic picks like "chicken" match any member (breast *or* thigh).
2. **Walk a guided flow** — one filter per page (cuisine, meal, diet, allergens, dislikes & time), with Back/Next and a URL for every step. Earlier answers narrow later ones: picking Vegan grays out the allergens it already guarantees (dairy, eggs, fish, shellfish) instead of asking you to redundantly re-pick them. An editable review screen shows everything before you search.
3. **Get ranked recipes** — hybrid SQL + vector retrieval, fused and hard-filtered for diet/allergen/time, ranked by pantry match with a plain-English "why." Ranking also gently favors recipes similar to ones you've saved, cooked, or liked — a lightweight personalization term applied strictly after every safety filter, so it can reorder but never surface something unsafe. If strict filters match nothing, it **relaxes the soft ones and shows the closest matches** rather than a dead end.
4. **Curate the results** — save a recipe for later, add it straight to a meal plan, or dismiss one you're not interested in (it drops out of the list and teaches future rankings to favor it less).
5. **Open a recipe** — an enriched method (prep state + cooking cues), serving-size scaling, a cook-along ingredient checklist, per-serving nutrition, provenance/attribution, and a quick "Made this" / like.
6. **Adapt it** — swap any ingredient (curated + LLM-suggested alternatives, or free-text), or remove one and let the assistant omit it or substitute the best alternative — with the steps, allergens, diet labels, and nutrition all re-derived.
7. **Shop the gap** — a shopping list of what you're missing, either for one recipe or consolidated across an entire meal plan.

## Features

**Discovery & ranking**
- A guided, one-filter-per-page flow (pantry → cuisine → meal → diet → allergens → dislikes/time → review → results) — every step is a real URL, Back/Forward work, and answers persist across a refresh.
- **Cross-step awareness:** a diet choice grays out (and won't let you redundantly re-add) allergens it already guarantees excluded — e.g. Vegan implies dairy/eggs/fish/shellfish, Vegetarian implies fish/shellfish, Gluten-free implies gluten. Grounded in the same rule the backend uses to derive those labels, not a guess.
- Pantry-based hybrid retrieval (deterministic SQL ingredient match **+** pgvector semantic search, fused with Reciprocal Rank Fusion).
- Hard filters (diet, allergens, time, cuisine, meal type, nutrition thresholds) applied post-fusion so a semantically-similar but non-compliant recipe can never leak in.
- Weighted ranking with a human-readable `why`; disliked ingredients demoted, not excluded.
- **Learned personalization:** a per-user taste vector (mean embedding of recipes you've saved/cooked/liked, minus a fraction of ones you've dismissed) nudges ranking toward your taste. Applied strictly *after* every hard filter, so it can only reorder the already-safe set — it can be disabled outright, and it's A/B-gated per session (a `control` arm never personalizes, so the effect can actually be measured).
- **Graceful fallbacks:** `substitution_first` (reachable by swapping something you have), `shopping_assisted` (closest + what to buy), and `relaxed` (soft filters set aside when nothing matches — diet/allergen never relaxed).
- Free-text pantry parsing ("half a bag of spinach and a couple eggs") via a fast LLM pass, merged into retrieval.

**Recipe interaction**
- Full recipe detail with pantry-aware ingredient tokens and provenance.
- **Serving-size scaling** (pure client, handles fractions and source-worded measures).
- **Substitutions:** curated table swaps **plus** LLM-suggested alternatives (ratio, note, diet effect), and a free-text "type another…" box for anything.
- **Remove an ingredient:** the assistant omits it (adjusting the method) or substitutes the best alternative, then re-derives steps, allergens, diet, and nutrition.
- **Lazy method enrichment:** on first view a recipe's terse source steps are rewritten with prep state and cooking cues, blank spice quantities are filled in, and junk/typo lines are cleaned — computed once, cached globally, shown behind a skeleton.
- **Cook-along checklist:** tick ingredients off as you use them (strikethrough, per-line, session-only).
- Post-swap/removal nutrition and allergen deltas, flagged when estimated.

**Saving, planning & feedback**
- **Save** any recipe (from a result card or its detail page) into a Saved list you can return to.
- **Meal plans:** group recipes under a named plan with a free-text label per item ("Mon dinner"), and pull one **consolidated shopping list across the whole plan** — the pantry is excluded automatically.
- **Feedback loop:** mark a recipe "Made this" or like it from its detail page; **dismiss** a result you're not interested in directly from the results list — it disappears from that view and feeds the personalization signal above (there's deliberately no separate dislike control on the recipe page; dismiss is the one place a negative signal comes from).
- The append-only interaction log behind all of this also powers avoid-repeat recommendations and the recency-aware agent prompt.

**Personalization & safety**
- Per-user pantry, saved filter defaults, dislikes, and recency-aware avoid-repeats.
- Diet / allergen / nutrition are **derived from canonical ingredient properties**, never hand-tagged, with a keyword safety backstop so an unmatched meat/fish/egg line can't mislabel a dish vegan.
- Google sign-in (Auth.js → HS256 bearer verified by the API); open dev mode via an `X-User-Key` header.

**Agentic layers**
- A single-agent tool-calling loop (`/v1/agent/recommend`) with a **deterministic validator + repair loop** and a hard fallback to a constraint-clean plan.
- A multi-agent **LangGraph** orchestrator (`/v1/orchestrate/plan`) — pantry analyst → recipe planner → safety/nutrition → shopping → supervisor, with session checkpointing.
- A **7-tool registry** (search, allergen check, substitutions, nutrition, shopping list, pantry read, meal-plan write) shared by both agent engines and exposed over **MCP** (stdio) for any MCP client.

**Analytics & observability**
- Lightweight event capture (results shown, recipe opened, cooked, saved, dismissed) tagged with a persisted per-browser session id — fire-and-forget, never blocks the UI.
- Deterministic session-level A/B bucketing (a `ranking_ab` experiment: `control` vs `personalized`) with a per-variant summary endpoint, so personalization's effect is measurable, not just assumed.
- An admin-gated metrics rollup over telemetry that's already being logged — request latency (p50/p95), degraded/repair rates, constraint-violation counts, token usage, and cache hit-rate — read-only, fail-closed behind a token, no new data model.

## How It Works

```text
┌────────────────────────────────────────────────────────────────┐
│                    Frontend  (Next.js / React)                  │
│   guided paged flow (pantry→filters→review→results) · recipe    │
│   detail · swap & remove · checklist · serving scaling ·        │
│   saved · meal plans · feedback (made this/like/dismiss) ·      │
│   Google sign-in                                                │
└───────────────────────────────┬────────────────────────────────┘
                                 │  JSON request
                                 │  (X-User-Key dev · Bearer JWT prod)
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                   API Gateway  (FastAPI · /v1)                  │
│           CORS · auth (disabled | jwt) · request schemas        │
└───────────────────────────────┬────────────────────────────────┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│  Recommend endpoint  ·  Redis cache (key: pantry+filters+mode  │
│  +user+variant; skipped entirely for personalized responses,   │
│  which are inherently per-user and feedback-driven)            │
└──────────────┬──────────────────────────────────┬──────────────┘
          hit  │                                   │  miss
               ▼                                   ▼
        return cached           ┌───────────────────────────────────┐
                                │   Retrieval Service               │
                                │   SQL ingredient-match  ⨉         │
                                │   pgvector KNN  →  RRF fusion      │
                                └────────────────┬──────────────────┘
                                                 ▼
                                ┌───────────────────────────────────┐
                                │   Rules / Filter Engine (safety)  │
                                │   diet · allergens · time ·       │
                                │   cuisine · meal · nutrition      │
                                │   (hard filters, applied          │
                                │   POST-fusion so nothing leaks)   │
                                └────────────────┬──────────────────┘
                                                 ▼
                                ┌───────────────────────────────────┐
                                │   Ranking  +  "why"               │
                                │   dislikes demoted (soft) ·       │
                                │   personalization term (taste     │
                                │   vector from saved/cooked/liked, │
                                │   A/B-gated, safety-fenced) ·     │
                                │   relax soft filters if empty ·   │
                                │   fallback mode → normal /        │
                                │   substitution_first /            │
                                │   shopping_assisted / relaxed     │
                                └────────────────┬──────────────────┘
                                                 │
   LLM-assisted paths                            │
   (recipe enrich · swap · remove ·              │
    agent / LangGraph ── MCP)                    │
              │                                  │
              ▼                                  │
┌───────────────────────────────────┐           │
│   LLM Adapter (guarded, fail-open)│           │
│   Claude sonnet / haiku ·         │           │
│   structured output · tool calls  │           │
└─────────────────┬─────────────────┘           │
                  ▼                              │
┌───────────────────────────────────┐           │
│   Validator / Safety Net (det.)   │           │
│   re-check recipe/diet/allergen/  │           │
│   time vs DB · repair loop →      │           │
│   constraint-clean fallback ·     │           │
│   re-derive diet/allergen/        │           │
│   nutrition after any edit        │           │
└─────────────────┬─────────────────┘           │
                  └───────────────┬──────────────┘
                                  ▼
┌────────────────────────────────────────────────────────────────┐
│                       Response Builder                         │
│   ranked recipes + why · substitutions · adapted steps ·       │
│   nutrition deltas · shopping list (missing items)             │
└───────────────────────────────┬────────────────────────────────┘
                                 ▼
                         Frontend (render)
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                    Logging & Evaluation                        │
│   generation_events · agent_traces · online events (shown/     │
│   opened/cooked/saved/dismissed) + A/B summary · cache metrics  │
│   · offline eval harnesses (retrieval hit@k / MRR · agent       │
│   pass-rate / cost) · admin metrics rollup (GET /v1/admin/…)   │
└────────────────────────────────────────────────────────────────┘
```

Basic recommendations run the deterministic spine (retrieval → filter → rank → fallback) with **no LLM in the hot path**; the LLM Adapter + Validator/Safety Net sit on the paths that do use a model — free-text pantry parsing, recipe enrichment, swap/remove adaptation, and the agent/orchestrator endpoints. Personalization is also LLM-free — a cosine similarity over existing recipe embeddings, cached in Redis per user.

Everything the LLM produces is **re-validated deterministically** against the database (recipe exists, allergens, diet, time), and every generation is logged (`generation_events`, `agent_traces`).

## AI & LLM Design

- **Hybrid RAG** grounded entirely in the internal corpus — no hallucinated recipes; the model shortlists, adapts, and explains, it doesn't invent.
- **Structured outputs** via Anthropic's typed `messages.parse(output_format=…)` with Pydantic schemas; kept small deliberately (a lesson learned: large/nested schemas blow the constrained-decoding grammar budget).
- **Tool/function calling** for deterministic checks (search, allergens, substitutions, nutrition, shopping list, pantry read, meal-plan write — 7 tools) — the LLM selects tools, code does the work.
- **Validation & repair loop** — violations are fed back to the model (capped), then a deterministic constraint-clean plan is the hard floor (`degraded=true`).
- **Fail-open everywhere** — with no API key or on an LLM error, every path degrades to the deterministic result and still returns 200.
- **Cost/latency control** — Redis cache on the fast path; `haiku` for cheap parsing, `sonnet` for reasoning; the LangGraph engine measured ~4.8× cheaper / ~2.7× faster than the raw loop for the same correctness.
- **Offline evaluation harnesses** — retrieval hit@k / MRR / constraint-violation counts, agent pass-rate / repair-success / cost, across structured, fuzzy, and regional gold sets.

## Technology Stack

**Frontend** — Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/Radix · TanStack Query 5 · Auth.js (NextAuth v5, Google OAuth) · next-themes

**Backend** — FastAPI · SQLAlchemy 2 · PostgreSQL + pgvector · Redis · Alembic (12 migrations) · Python 3.12

**AI/ML** — Anthropic Claude (Sonnet + Haiku behind a thin adapter) · sentence-transformers (MiniLM, 384-dim, HNSW cosine) · numpy (personalization cosine similarity, metrics percentiles) · LangGraph + langchain-anthropic · MCP (stdio server)

**Dev/Ops** — Docker Compose (db · redis · backend) · Pytest · GitHub Actions CI (backend pytest + frontend lint/build) · Black/isort/Flake8/ESLint

## API

Base: `http://localhost:8000`. All app routes are under `/v1`. Auth is an `X-User-Key` header in dev, or an `Authorization: Bearer` HS256 token from the Auth.js session when Google sign-in is configured.

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness + Postgres/Redis dependency checks |
| `GET /v1/config` | Nutrition-goal thresholds (source of truth for the UI) |
| `GET /v1/ingredients?q=` | Ingredient autocomplete (canonical + aliases + generics) |
| `GET /v1/cuisines` | Cuisine taxonomy with live per-node counts |
| `GET /v1/pantry` · `PUT /v1/pantry` | Per-user pantry (staples, alias resolution) |
| `POST /v1/pantry/parse` | Free-text pantry → recognized ingredients (LLM parse; doesn't mutate the pantry) |
| `GET /v1/profile/{key}` · `PUT /v1/profile/{key}` | Saved diet/allergen/dislikes/cuisine defaults |
| `POST /v1/feedback` | Record an interaction (recipe_id, action — cooked/uncooked/liked/disliked/unrated) |
| `GET /v1/feedback/{key}` | Derived per-recipe feedback state (made / rating) |
| `GET /v1/saved` · `POST /v1/saved` · `DELETE /v1/saved/{id}` | Bookmark a recipe (idempotent add) |
| `GET /v1/plans` · `POST /v1/plans` · `GET /v1/plans/{id}` · `DELETE /v1/plans/{id}` | Meal plans |
| `POST /v1/plans/{id}/items` · `DELETE /v1/plans/{id}/items/{recipe_id}` | Add/remove a recipe in a plan |
| `GET /v1/plans/{id}/shopping-list` | Combined shopping list across a plan's recipes, pantry excluded |
| `POST /v1/recommendations` | Hybrid retrieval + ranking + fallback modes (+ personalization, A/B variant) |
| `POST /v1/shopping-list` | Aggregate missing ingredients across recipes |
| `POST /v1/substitutions` | Curated + LLM substitution suggestions for an ingredient |
| `GET /v1/recipes/{id}` | Recipe detail (prefers enriched steps/measures) |
| `POST /v1/recipes/{id}/enrich` | Lazy method + missing-quantity enrichment (cached) |
| `POST /v1/recipes/{id}/modify` | Swap or remove an ingredient; re-derive labels/nutrition/steps |
| `POST /v1/agent/recommend` | Single-agent tool-calling loop + validator/repair |
| `POST /v1/orchestrate/plan` | LangGraph multi-agent plan (session-checkpointed) |
| `GET /v1/traces/{session_id}` | Orchestrator run traces |
| `GET /v1/metrics/cache` | Recommendation cache hit/miss metrics |
| `POST /v1/events` | Log an analytics event (session-scoped, fire-and-forget) |
| `GET /v1/experiments/{name}/summary` | Per-variant event counts for an A/B experiment |
| `GET /v1/admin/metrics` | Admin-gated observability rollup (latency, degraded/repair rates, tokens, cache, events) |

## Data & Ingestion

- **~7,600 recipes** (144 curated seed + ~6,700 Archana's Kitchen + ~700 TheMealDB) with provenance, attribution, and license notes; all embedded (MiniLM/HNSW).
- **275 canonical ingredients** with per-100g nutrition, allergens, and diet properties; source ingredient names are normalized to canonical via a parser + alias matcher.
- **Own-the-data pipeline** (`backend/scripts/ingest/`): parse → canonical match → derive diet/allergen/nutrition → dedup upsert. Scraped datasets stay gitignored; CI seeds only the 144-recipe baseline.
- **Canonicalization backfill** (`backend/scripts/backfill_ingredients.py`): LLM-assisted mapping of unmapped source names to canonical (cheese→paneer, sunflower oil→vegetable oil, Devanagari नमक→salt, …), with an accuracy audit that drops loose stand-ins, plus a clean from-raw re-parse. A read-only verifier (`verify_backfill.py`) diffs a fresh parse against the DB (~99% agreement).

## Local Development

Prerequisites: Docker + Docker Compose, Node 20+, Python 3.12. An `ANTHROPIC_API_KEY` unlocks the LLM features (everything fails open without one).

```bash
# 1. Backend services (Postgres+pgvector, Redis, API)
docker compose up -d --build

# 2. Seed + embed the baseline corpus (from backend/, in a venv with requirements.txt)
python scripts/seed.py
python scripts/embed_recipes.py

# 3. Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Config is via environment variables (`.env` for the backend, `frontend/.env.local` for the web app) — `AUTH_MODE` (`disabled` | `jwt`), `AUTH_SHARED_SECRET`, `CORS_ORIGINS`, `ANTHROPIC_API_KEY`, and the Google OAuth client for sign-in. Optional: `PERSONALIZATION_ENABLED` (default on), `EXPERIMENT_VARIANTS` (default `control,personalized`), and `ADMIN_TOKEN` to unlock `GET /v1/admin/metrics` (unset = the route stays locked). The large scraped corpora and the alias-backfill scripts run manually (see `backend/scripts/`).

## Testing & CI

- `pytest` in `backend/` — retrieval, ranking, derivation, modify/enrich, agent loop, validator, orchestrator, and API tests. LLM calls are mocked; DB-backed tests skip automatically if Postgres is unreachable, and discover rows dynamically (never hardcode ids).
- `npm run lint && npm run build` in `frontend/`.
- GitHub Actions runs the backend suite (auth disabled) and the frontend lint/build on every push. CI seeds only the 144-recipe baseline, so scraped-corpus data quality is verified locally, not in CI.

## Repository Structure

```text
backend/
  app/
    api/            # FastAPI routers (recommendations, recipes, pantry, saved, plans, events, admin, agent, orchestrate, …)
    agent/          # tool registry (7 tools), single-agent loop, prompts
    orchestrator/   # LangGraph graph + nodes
    services/       # retrieval, ranking, personalization, modify, enrich, derivation, ingredients,
                     #   fallback, saved, plans, events, experiments, metrics, cache
    llm/            # Anthropic adapter
    models/ · schemas/ · core/ · evals/ · tests/
  alembic/          # migrations (0001–0012)
  scripts/          # seed, embed, ingestion pipeline, canonicalization backfill
  seed_data/        # ingredients.json (canonical vocab), recipes.json, substitutions.json
frontend/
  app/              # App Router pages: / landing, /app pantry, /app/filters/[step], /app/results,
                     #   /app/saved, /app/plans(/[id]), /recipes/[id], /login
  components/       # filters (steps/), pantry, recipe, results, landing, ui
  lib/              # api client, hooks, query keys, flow/ (paged-flow context + steps), track.ts
docker-compose.yml · README.md
```

## Project Status

The product described above — pantry → guided flow → ranked, safe recipes → save/plan/adapt → shop, plus personalization, online analytics, and an observability endpoint — is fully implemented and tested. There's no active roadmap queued right now.

## License

License to be determined. The scraped recipe datasets (Archana's Kitchen, TheMealDB) are used under their respective terms with attribution preserved and are not redistributed.
