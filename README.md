# NourishAI

NourishAI is an AI-powered recipe recommendation platform that converts pantry ingredients into practical meal options. The system is designed to combine deterministic retrieval, rules-based validation, and LLM generation to produce recipes that are relevant, safe, and user-specific.

## Table of Contents
- [Project Status](#project-status)
- [Current Implementation](#current-implementation)
- [Target Product Capabilities](#target-product-capabilities)
- [AI and LLM Capabilities](#ai-and-llm-capabilities)
- [LangChain, LangGraph, and MCP](#langchain-langgraph-and-mcp)
- [Agent Development and System Design Skills Demonstrated](#agent-development-and-system-design-skills-demonstrated)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Local Development Setup](#local-development-setup)
- [API Endpoints](#api-endpoints)
- [Repository Structure](#repository-structure)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Project Status
This repository is in early development.

- Infrastructure and service scaffolding are in place.
- Core product workflows (pantry intake, recommendation orchestration, tool-driven validation, and full frontend UX) are planned but not fully implemented.

## Current Implementation

### Backend
- FastAPI application initialized in `backend/app/main.py`.
- Health endpoint available at `/health` with dependency checks for PostgreSQL and Redis.
- Configuration management via environment variables and Pydantic settings.

### Data Layer
- PostgreSQL + pgvector container defined in `docker-compose.yml`.
- Redis container defined in `docker-compose.yml`.
- Seed schema and example recipe data in `db/init/010_seed.sql`.

### Frontend
- Next.js application scaffold available in `frontend/`.
- Landing page placeholder in `frontend/app/page.tsx`.

## Target Product Capabilities
- Pantry-based recipe search and ranking.
- Ingredient substitution recommendations.
- Dietary and allergen-aware filtering.
- Time-constrained recipe generation (for example, quick-meal mode).
- Shopping list generation for missing ingredients.
- Preference-aware personalization from user feedback.

## AI and LLM Capabilities
NourishAI is designed to showcase production-oriented LLM patterns:

- Retrieval-augmented generation (RAG) grounded in internal recipe data.
- Constraint-aware generation for diet, allergen, and time limits.
- Structured model outputs validated with typed schemas.
- Tool/function calling for deterministic checks (nutrition, substitutions, shopping list composition).
- Validation and repair loops to enforce policy and reliability requirements.

## LangChain, LangGraph, and MCP

### LangChain
- Compose retrieval, prompting, tool-use, and output parsing chains.
- Build reusable modules for recommendation and substitution tasks.

### LangGraph
- Model multi-step orchestration as an explicit workflow graph.
- Use conditional branches for validation failures and retry/repair paths.
- Add persistent conversational state for personalization across sessions.

### MCP (Model Context Protocol)
- Expose internal capabilities as typed tools, such as:
  - `search_recipes`
  - `check_inventory`
  - `check_allergens`
  - `build_shopping_list`
  - `save_meal_plan`
- Enable safe, auditable action execution by LLM-driven flows.

## Agent Development and System Design Skills Demonstrated

### AI Agent Development
- Goal decomposition into deterministic and generative subtasks.
- Tool selection and execution instead of unconstrained free-text generation.
- Self-correction loops with validation-based retries.
- Memory-informed personalization using explicit user feedback.
- Action-oriented outputs (meal plans, shopping lists, pantry updates).

### Scalable AI System Design
- Clear service boundaries (API, orchestration, retrieval, validation, generation, analytics).
- Hybrid fast path (cache/retrieval) plus LLM path for cost and latency control.
- Reliability patterns including health checks, retry strategy, and fallback behavior.
- Observability requirements for latency, failures, quality metrics, and model usage.
- Evaluation strategy including offline constraint pass-rate testing and online experiments.

## Architecture

```text
┌────────────────────────┐
│        Frontend        │  React/Next: pantry input, filters,
│  (Web/Mobile UI)       │  dietary prefs, history
└──────────┬─────────────┘
           │ JSON request
           ▼
┌────────────────────────┐
│      API Gateway       │  Auth, rate limit, request schema check
└──────────┬─────────────┘
           │
     ┌─────▼─────────────────────────────────────────────────────────┐
     │                    Orchestrator Service                       │
     │     (decides fast path vs. LLM path; logs everything)        │
     └─────┬───────────────┬─────────────────────────────┬───────────┘
           │               │                             │
   ┌───────▼──────┐  ┌─────▼─────────────────┐    ┌──────▼─────────┐
   │ Cache Layer  │  │  Retrieval Service    │    │  Rules/Filter  │
   │ (Redis)      │  │  (Vector + SQL search)│    │  Engine        │
   │ key: pantry+ │  │  - Vector DB          │    │  - Diet rules  │
   │ prefs+goal   │  │    (FAISS/pgvector)   │    │  - Allergens   │
   └───────┬──────┘  │  - SQL DB (recipes,   │    │  - Cost/time   │
           │         │    nutrition, tags)   │    └──────┬─────────┘
       hit │ miss    └───────────┬───────────┘           │
           │                     │                       │
           ▼                     │ top-K candidates      │
   ┌─────────────────┐           │                       │
   │ Return cached   │◄──────────┘                       │
   │ result fast     │                                   │
   └─────────────────┘                                   │
                                                         │
                                                         ▼
                                            ┌──────────────────────────┐
                                            │  Validation Services     │
                                            │  - Nutrition API check   │
                                            │  - Units/steps checker   │
                                            │  - Has-all-ingredients   │
                                            └──────────┬───────────────┘
                                                       │
                                                       ▼
                                      ┌─────────────────────────────────┐
                                      │   LLM Adapter (guarded calls)  │
                                      │   - System prompt constraints   │
                                      │   - Few-shot examples           │
                                      │   - Tool calls allowed          │
                                      └──────────┬──────────────────────┘
                                                 │
                               ┌─────────────────▼─────────────────┐
                               │  Post-Processor / Safety Net      │
                               │  - Re-validate diet/allergens     │
                               │  - Fix units/steps, enforce caps  │
                               │  - Fallback to non-LLM variant    │
                               └─────────────────┬─────────────────┘
                                                 │
                                                 ▼
                                 ┌───────────────────────────────────┐
                                 │  Response Builder                 │
                                 │  - Final recipe + steps           │
                                 │  - Substitutions list             │
                                 │  - Shopping list (missing items)  │
                                 └─────────────────┬─────────────────┘
                                                 │
                                                 ▼
                                      ┌────────────────────────┐
                                      │ Frontend (render)      │
                                      │ Ratings and feedback   │
                                      └──────────┬─────────────┘
                                                 │
                                                 ▼
                              ┌────────────────────────────────────┐
                              │  Analytics and Evaluation Pipeline │
                              │  - A/B tests (prompt vs. hybrid)  │
                              │  - Success metrics (click, cook,  │
                              │    save, remake, time-to-answer)  │
                              │  - Offline eval (constraint pass) │
                              └────────────────────────────────────┘
```

## Technology Stack

### Frontend
- Next.js
- React
- TypeScript
- Material UI

### Backend
- FastAPI
- SQLAlchemy
- PostgreSQL (pgvector)
- Redis

### AI/ML
- OpenAI API
- sentence-transformers
- scikit-learn
- PyTorch

### Development and Operations
- Docker and Docker Compose
- Pytest
- Linting and formatting tools (Black, isort, Flake8, ESLint, Prettier)

## Local Development Setup

### Option 1: Full setup script
```bash
./dev-setup.sh
```

### Option 2: Make targets
```bash
make setup
```

### Option 3: Manual setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
make up
./start-api.sh
```

## API Endpoints
- `GET /` - service metadata and links.
- `GET /health` - health status of API dependencies (database and cache).

## Repository Structure

```text
backend/
  app/
    api/
    core/
    tests/
frontend/
  app/
db/
  init/
README.md
DEV-SETUP.md
docker-compose.yml
```

## Roadmap
- Implement pantry intake and recommendation endpoints.
- Add retrieval + ranking over seeded and expanded recipe datasets.
- Integrate LLM tool-calling with strict schema validation.
- Build end-user frontend flows for input, recommendations, and feedback.
- Add evaluation harness, observability, and A/B testing support.

## Contributing
Contributions are welcome. Please open an issue describing the proposal before submitting major changes.

## License
License definition is pending.
