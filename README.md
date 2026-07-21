# NourishAI

NourishAI turns what's in your pantry into recipes you can actually cook tonight. Tell it your ingredients and tonight's mood — cuisine, meal, diet, allergens, time, nutrition goals — and it returns ranked, diet- and allergen-safe recipes drawn from a ~7,600-recipe corpus, with smart substitutions, an adaptive method, serving-size scaling, and a shopping list for anything you're missing.

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
- [Roadmap — Upcoming Features](#roadmap--upcoming-features)
- [License](#license)

## What It Does

1. **Stock a pantry** — add ingredients (with autocomplete over a canonical vocabulary and aliases) plus everyday staples; it's saved per user. Generic picks like "chicken" match any member (breast *or* thigh).
2. **Set tonight's mood** — a short questionnaire: cuisine (two-level taxonomy), meal type, diet, allergens to avoid, dislikes, time cap, and nutrition goals (high-protein / low-fat / low-carb / low-calorie, with the actual thresholds shown).
3. **Get ranked recipes** — hybrid SQL + vector retrieval, fused and hard-filtered for diet/allergen/time, ranked by pantry match with a plain-English "why." If strict filters match nothing, it **relaxes the soft ones and shows the closest matches** rather than a dead end.
4. **Open a recipe** — an enriched method (prep state + cooking cues), serving-size scaling, a cook-along ingredient checklist, per-serving nutrition, and provenance/attribution.
5. **Adapt it** — swap any ingredient (curated + LLM-suggested alternatives, or free-text), or remove one and let the assistant omit it or substitute the best alternative — with the steps, allergens, diet labels, and nutrition all re-derived.
6. **Shop the gap** — a consolidated shopping list of what you're missing across chosen recipes.

## Features

**Discovery & ranking**
- Pantry-based hybrid retrieval (deterministic SQL ingredient match **+** pgvector semantic search, fused with Reciprocal Rank Fusion).
- Hard filters (diet, allergens, time, cuisine, meal type, nutrition thresholds) applied post-fusion so a semantically-similar but non-compliant recipe can never leak in.
- Weighted ranking with a human-readable `why`; disliked ingredients demoted, not excluded.
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

**Personalization & safety**
- Per-user pantry, saved filter defaults, dislikes, and recency-aware avoid-repeats.
- Diet / allergen / nutrition are **derived from canonical ingredient properties**, never hand-tagged, with a keyword safety backstop so an unmatched meat/fish/egg line can't mislabel a dish vegan.
- Google sign-in (Auth.js → HS256 bearer verified by the API); open dev mode via an `X-User-Key` header.

**Agentic layers**
- A single-agent tool-calling loop (`/v1/agent/recommend`) with a **deterministic validator + repair loop** and a hard fallback to a constraint-clean plan.
- A multi-agent **LangGraph** orchestrator (`/v1/orchestrate/plan`) — pantry analyst → recipe planner → safety/nutrition → shopping → supervisor, with session checkpointing.
- The tool registry is also exposed over **MCP** (stdio) for use from MCP clients.

## How It Works

```text
Frontend (Next.js)  ──JSON──►  FastAPI
  pantry · filters                │
  recipe UI                       ▼
                        ┌───────────────────────┐
                        │  Recommend endpoint    │
                        │  Redis cache (key:      │
                        │   pantry+filters+mode)  │
                        └───────┬────────────────┘
                          hit  │  miss
                    ┌──────────┘        └───────────────┐
                    ▼                                    ▼
             return cached                      Hybrid Retrieval
                                          SQL ingredient-match ⨉ pgvector
                                          → RRF fusion → hard filters
                                                     │ top-K
                                                     ▼
                                          Ranking (weighted + why)
                                                     │
                                          empty? → relax soft filters
                                                     │
                                                     ▼
                                          Fallback classifier
                                       (normal / substitution_first /
                                        shopping_assisted / relaxed)
                                                     │
                                                     ▼
                                              Response (results,
                                              mode, explanation)

Recipe detail ── enrich (LLM, cached) · modify/remove (LLM + deterministic
                 re-derivation) · scale (client) · shopping list

Agent path   ── tool-calling loop / LangGraph orchestrator ── MCP (stdio)
                deterministic validator + repair; everything logged
```

Everything the LLM produces is **re-validated deterministically** against the database (recipe exists, allergens, diet, time), and every generation is logged (`generation_events`, `agent_traces`).

## AI & LLM Design

- **Hybrid RAG** grounded entirely in the internal corpus — no hallucinated recipes; the model shortlists, adapts, and explains, it doesn't invent.
- **Structured outputs** via Anthropic's typed `messages.parse(output_format=…)` with Pydantic schemas; kept small deliberately (a lesson learned: large/nested schemas blow the constrained-decoding grammar budget).
- **Tool/function calling** for deterministic checks (search, allergens, substitutions, nutrition, shopping list) — the LLM selects tools, code does the work.
- **Validation & repair loop** — violations are fed back to the model (capped), then a deterministic constraint-clean plan is the hard floor (`degraded=true`).
- **Fail-open everywhere** — with no API key or on an LLM error, every path degrades to the deterministic result and still returns 200.
- **Cost/latency control** — Redis cache on the fast path; `haiku` for cheap parsing, `sonnet` for reasoning; the LangGraph engine measured ~4.8× cheaper / ~2.7× faster than the raw loop for the same correctness.
- **Offline evaluation harnesses** — retrieval hit@k / MRR / constraint-violation counts, agent pass-rate / repair-success / cost, across structured, fuzzy, and regional gold sets.

## Technology Stack

**Frontend** — Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/Radix · TanStack Query 5 · Auth.js (NextAuth v5, Google OAuth) · next-themes

**Backend** — FastAPI · SQLAlchemy 2 · PostgreSQL + pgvector · Redis · Alembic (10 migrations) · Python 3.12

**AI/ML** — Anthropic Claude (Sonnet + Haiku behind a thin adapter) · sentence-transformers (MiniLM, 384-dim, HNSW cosine) · LangGraph + langchain-anthropic · MCP (stdio server)

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
| `GET /v1/profile/{key}` · `PUT /v1/profile/{key}` | Saved diet/allergen/dislikes/cuisine defaults |
| `POST /v1/feedback` | Record an interaction (recipe_id, action) |
| `POST /v1/recommendations` | Hybrid retrieval + ranking + fallback modes |
| `POST /v1/shopping-list` | Aggregate missing ingredients across recipes |
| `POST /v1/substitutions` | Curated + LLM substitution suggestions for an ingredient |
| `GET /v1/recipes/{id}` | Recipe detail (prefers enriched steps/measures) |
| `POST /v1/recipes/{id}/enrich` | Lazy method + missing-quantity enrichment (cached) |
| `POST /v1/recipes/{id}/modify` | Swap or remove an ingredient; re-derive labels/nutrition/steps |
| `POST /v1/agent/recommend` | Single-agent tool-calling loop + validator/repair |
| `POST /v1/orchestrate/plan` | LangGraph multi-agent plan (session-checkpointed) |
| `GET /v1/traces/{session_id}` | Orchestrator run traces |
| `GET /v1/metrics/cache` | Recommendation cache hit/miss metrics |

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

Config is via environment variables (`.env` for the backend, `frontend/.env.local` for the web app) — `AUTH_MODE` (`disabled` | `jwt`), `AUTH_SHARED_SECRET`, `CORS_ORIGINS`, `ANTHROPIC_API_KEY`, and the Google OAuth client for sign-in. The large scraped corpora and the alias-backfill scripts run manually (see `backend/scripts/`).

## Testing & CI

- `pytest` in `backend/` — retrieval, ranking, derivation, modify/enrich, agent loop, validator, orchestrator, and API tests. LLM calls are mocked; DB-backed tests skip automatically if Postgres is unreachable, and discover rows dynamically (never hardcode ids).
- `npm run lint && npm run build` in `frontend/`.
- GitHub Actions runs the backend suite (auth disabled) and the frontend lint/build on every push. CI seeds only the 144-recipe baseline, so scraped-corpus data quality is verified locally, not in CI.

## Repository Structure

```text
backend/
  app/
    api/            # FastAPI routers (recommendations, recipes, pantry, agent, orchestrate, …)
    agent/          # tool registry, single-agent loop, prompts
    orchestrator/   # LangGraph graph + nodes
    services/       # retrieval, ranking, modify, enrich, derivation, ingredients, fallback
    llm/            # Anthropic adapter
    models/ · schemas/ · core/ · evals/ · tests/
  alembic/          # migrations (0001–0010)
  scripts/          # seed, embed, ingestion pipeline, canonicalization backfill
  seed_data/        # ingredients.json (canonical vocab), recipes.json, substitutions.json
frontend/
  app/              # App Router pages (/ landing, /app, /recipes/[id], /login)
  components/       # filters, pantry, recipe, results, landing, ui
  lib/ · types/     # api client, hooks, query keys
docker-compose.yml · README.md · ROADMAP.md
```

## Roadmap — Upcoming Features

The core product (pantry → ranked, safe recipes → adapt → shop) is complete. The following are the planned next capabilities — what each should look like from the user's side. The implementation approach for each is drafted in **[ROADMAP.md](ROADMAP.md)**.

1. **Ratings & feedback loop (UI).** On a recipe: a "Made this," a thumbs up/down, and a "Save." On a result card: quick save/dismiss. These capture the signals the backend already has a home for (`interaction_history`), turning the one-way "recommended" log into a real loop. *Looks like:* small, unobtrusive controls on the recipe header and result cards, with a lightweight toast confirmation and a "Saved / Cooked" state that persists per user.

2. **Saved recipes & meal planning.** A "Saved" area the user can return to, and the ability to add recipes to a simple **meal plan** (e.g. a few dinners this week) whose combined shopping list is one tap away. *Looks like:* a saved/favorites list on `/app`, a "Add to plan" action, a `/plan` view with day slots, and a consolidated shopping list across the plan.

3. **Learned personalization.** Beyond explicit prefs, gently bias ranking from behavior — recipes similar to ones you saved/cooked rank higher; ones you dismissed sink. *Looks like:* no new UI, just better ordering over time, with a small "Because you liked …" explanation string, kept honest and overridable.

4. **Online analytics & A/B.** A minimal experimentation layer: assign a ranking/prompt variant per session, log outcome events (view, open, cook, save, time-to-answer), and compare variants. *Looks like:* invisible to users; a backend events table + a summary endpoint, and offline/online metric parity with the existing eval harnesses.

5. **Observability surface.** A small internal dashboard (or metrics endpoint set) for request latency, LLM cost/usage, failure/degraded rates, and constraint-violation counts — built on the data already logged in `generation_events` / `agent_traces`. *Looks like:* an admin-only `/metrics`-style page or Grafana-friendly JSON.

6. **Completing the MCP tool surface.** Add `check_inventory` (pantry as a first-class agent tool) and `save_meal_plan` (persist a plan) so an MCP client or the agent can read the pantry and write a plan, closing the loop between discovery and action.

## License

License to be determined. The scraped recipe datasets (Archana's Kitchen, TheMealDB) are used under their respective terms with attribution preserved and are not redistributed.
