# NourishAI — Current State (draft README)

> **Purpose of this file:** a factual, up-to-date snapshot of what actually
> runs today, meant to eventually replace `README.md`. `README.md` is kept as
> the aspirational product/architecture vision (point of inspiration for future
> upgrades); this file tracks reality. As of Stage 5.6 (2026-07-14).

NourishAI turns a pantry into ranked, diet/allergen-safe recipes with
substitutions and shopping lists. It layers four retrieval/generation tiers
behind one FastAPI service: deterministic SQL retrieval → hybrid RAG → a single
tool-calling agent → a LangGraph multi-agent orchestrator. A Next.js frontend
(pantry manager + stepped filter questionnaire) drives the fast deterministic
path.

## Build status (what's real)

| Stage | Scope | Status |
|---|---|---|
| 0 | Repair + walking skeleton (compose, Alembic, pytest) | ✅ |
| 1 | Base SQL retrieval, ranking, shopping list, Redis cache, eval harness | ✅ |
| 2 | Hybrid RAG — local embeddings + pgvector KNN, RRF fusion, LLM pantry-text parse, low-confidence fallback | ✅ |
| 3 | Single agent — raw Anthropic tool-calling loop, deterministic validator + repair, prompt versioning, profile/memory | ✅ |
| 4 | Multi-agent — LangGraph supervisor + specialists, session checkpointing, trace logging, MCP tool layer | ✅ |
| 5 | Frontend + Auth — Next 15 UI, pantry manager, filter wizard, results, Google OAuth bridge | ✅ 5.1–5.5 (5.5 code-complete; Google client pending), 5.6 in progress |
| 6 | Real recipe corpus (TheMealDB + Archana's + Edamam), regional Indian | ⬜ planned |
| 7 | Recipe interaction (in-app render, scaling, substitution modification) | ⬜ roadmap |

Backend test suite: **~105 tests** (2 embedder tests gated behind
`RUN_EMBEDDER_TESTS=1`). See `EVALUATION.md` for eval baselines.

## Technology stack (actual)

**Frontend** — Next.js 15 (App Router) · React 19 · TypeScript · Tailwind v4
(`@theme` in `globals.css`, no config) · shadcn/ui (Radix) · TanStack Query 5 ·
Auth.js (NextAuth v5 beta) + Google OAuth · native `fetch` (no axios).

**Backend** — FastAPI 0.139 · SQLAlchemy 2 · Alembic · PostgreSQL 16 + pgvector ·
Redis 7 · PyJWT (HS256 bearer bridge).

**AI / ML** — Anthropic Claude (`claude-haiku-4-5` parse, `claude-sonnet-5`
agent, `claude-opus-4-8` judge) behind a thin adapter · sentence-transformers
`all-MiniLM-L6-v2` (384-dim, local, CPU) · pgvector HNSW cosine KNN + Reciprocal
Rank Fusion · LangGraph + langchain-anthropic · MCP (stdio, edge adapter).

**Dev / Ops** — Docker Compose · pytest · black/isort/flake8/mypy · ESLint ·
GitHub Actions CI (`.github/workflows/ci.yml`).

## Quickstart

### 1. Backend + data stores (Docker)

```bash
cp .env.example .env          # adjust if needed; .env is gitignored
make up                        # postgres (pgvector) + redis + backend
```

Or run the backend on the host against the containerized stores:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
make migrate                   # alembic upgrade head
cd backend && python scripts/seed.py   # ~144 recipes / 99 ingredients / 51 subs
make api                       # uvicorn app.main:app --reload
curl -s localhost:8000/health  # {"status":"ok","db":true,"redis":true}
```

Optional — backfill embeddings for the hybrid vector arm (downloads the
sentence-transformers model once):

```bash
cd backend && ../.venv/bin/python scripts/embed_recipes.py
```

LLM features (pantry-text parsing, agent, orchestrator) need
`ANTHROPIC_API_KEY` in `.env`. Without it the code **fail-opens**: the
deterministic retrieval path still works; only free-text/agent demos are off.

### 2. Frontend

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                    # http://localhost:3000
```

The browser talks to FastAPI directly (CORS-enabled). In dev the app runs in
`AUTH_MODE=disabled` and identifies with an `X-User-Key` header. Google sign-in
turns on once `AUTH_GOOGLE_ID`/`SECRET` are set and `NEXT_PUBLIC_AUTH_ENABLED=true`
(see Auth below).

### 3. MCP server (optional)

```bash
make mcp-verify                # lists 5 tools + exercises two over stdio
make mcp                       # run the stdio server (attach to Claude Desktop)
```

## API endpoints

Interactive docs at `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service metadata |
| GET | `/health` | DB + Redis health |
| POST | `/v1/recommendations` | Ranked recipes (fast deterministic path; `pantry` or `pantry_text`) |
| POST | `/v1/shopping-list` | Aggregate missing ingredients across recipes |
| GET | `/v1/metrics/cache` | Recommendation cache hit/miss counters |
| POST | `/v1/substitutions` | Ingredient substitutions (diet-aware) |
| POST | `/v1/agent/recommend` | Single agent — tool-calling loop + validator/repair |
| POST | `/v1/orchestrate/plan` | Multi-agent LangGraph meal plan (session-aware) |
| GET | `/v1/traces/{session_id}` | Ordered agent/graph execution trace |
| GET | `/v1/ingredients?q=` | Ingredient autocomplete (prefix + alias) |
| GET / PUT | `/v1/pantry` | Per-user pantry (staples + current) |
| GET / PUT | `/v1/profile/{user_key}` | User profile (diet, allergens, dislikes) |
| POST | `/v1/feedback` | Record recipe interaction |

## Auth (Stage 5.5)

Two modes, selected by `AUTH_MODE`:

- **`disabled`** (default, dev) — API is open; identity comes from the
  `X-User-Key` header (`dev-user` by default). Keeps the whole suite green
  without tokens.
- **`jwt`** — the Next.js Auth.js layer mints an HS256 bearer (Google `sub` →
  `google:{sub}`) signed with `AUTH_SHARED_SECRET`; FastAPI verifies it and
  ignores `X-User-Key`.

To enable Google sign-in: create a Google Cloud OAuth **Web** client (JS origin
`http://localhost:3000`, redirect `http://localhost:3000/api/auth/callback/google`,
add test-user Gmails while the consent screen is in Testing mode), paste
`AUTH_GOOGLE_ID`/`AUTH_GOOGLE_SECRET` into `frontend/.env.local`, set
`NEXT_PUBLIC_AUTH_ENABLED=true`, then flip the backend to `AUTH_MODE=jwt`
(with a matching `AUTH_SHARED_SECRET`).

## Make targets

`make up | down | ps | logs` (compose) · `make api` (uvicorn) · `make test`
(pytest) · `make migrate` / `make revision m="…"` (Alembic) · `make psql` /
`make redis` (shells) · `make mcp` / `make mcp-verify`.

## Repository structure

```text
backend/
  app/
    api/            # routers: recommendations, shopping_list, substitutions,
                    #   agent, orchestrate, traces, ingredients, pantry,
                    #   profile, health, auth
    core/           # config, cuisine taxonomy
    models/         # SQLAlchemy models
    schemas/        # Pydantic request/response
    services/       # retrieval, ranking, embedder, shopping, cache, ingredients
    llm/            # Claude adapter
    agent/          # tool registry, loop, validator, prompts, tracing
    orchestrator/   # LangGraph state + graph
    evals/          # retrieval + agent eval harnesses
    mcp_server.py   # MCP stdio edge adapter
    tests/          # pytest suite
  alembic/          # migrations 0001–0007
  scripts/          # seed.py, embed_recipes.py, backfill_*, verify_mcp.py
  seed_data/        # recipes.json, ingredients.json, substitutions.json, eval/
frontend/
  app/              # App Router pages (/, /app, /login, /recipes/[id], api/auth)
  components/       # landing, pantry, filters, results, ui (shadcn)
  lib/              # api client, query keys, cuisines, hooks, auth-token
  types/            # api types mirroring backend schemas
docker-compose.yml
.github/workflows/ci.yml
EVALUATION.md       # eval methodology + baselines
```

## Continuous integration

`.github/workflows/ci.yml` runs on push to `main` and on PRs:

- **backend** — Python 3.12 with Postgres/pgvector + Redis services, `alembic
  upgrade head`, `python scripts/seed.py`, `pytest` (`AUTH_MODE=disabled`, no
  Anthropic key — LLM tests are mocked, embedder tests gated off).
- **frontend** — Node 20, `npm ci`, `npm run lint`, `npm run build`.

## License

License definition is pending (personal/family use; some planned recipe sources
in Stage 6 are attribution-only — not for public commercial deploy).
