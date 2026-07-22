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

Recommend flow: SQL ingredient-match + pgvector KNN candidates → RRF fusion → hard filters (diet/allergen/time) applied strictly after fusion → ranking (base score + personalization term) → fallback if the filtered set is empty. Personalization can only ever reorder an already-filtered set — it must never be able to surface a diet/allergen violation; if you touch `ranking.py` or `personalization.py`, preserve that ordering.

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
