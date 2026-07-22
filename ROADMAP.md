# NourishAI — Implementation Roadmap

**Status: all phases below are shipped.** This file is kept as the implementation-notes record of how each capability was built — useful context if you're extending one of them — not a queue of upcoming work. See the README's [Features](README.md#features) and [API](README.md#api) sections for the current, user-facing description of what exists today.

Each phase was scoped to the *existing* architecture — most reuse tables, endpoints, and components already in place. Originally ordered by impact-to-effort; built in the order: UX redesign → Phase 1 (feedback) → Phase 2 (saved/plans) → Phase 6 (MCP tools) → Phase 3 (personalization) → Phase 4 (analytics/A-B) → Phase 5 (observability).

**Conventions used throughout:** derive don't hand-tag; deterministic-first with LLM fail-open; keep user edits ephemeral unless persistence is the feature; per-user identity via `X-User-Key` (dev) / verified bearer (`jwt`); DB-backed tests discover rows dynamically; commit per slice with a live demo.

---

## UX Redesign — Immersive paged flow  ·  medium  ·  (can go first)

**Why:** replace the single dense `/app` screen with a guided, **one-thing-per-page** experience. It reshapes the shell the feature phases below then live in (results/ratings/save land on the new pages), so it's reasonable to do this before or alongside Phase 1.

**Flow & screens**
1. **Pantry page** (`/app`) — `PantryManager` (structured combobox **+** the free-text "describe what you have" box) and staples; primary CTA **"Start cooking."**
2. **Filter pages — one filter per page:** Cuisine → Meal → Diet & goals → Avoid (allergens) → Dislikes & time. Each is a full screen with a single filter component, a slim progress indicator, and a **Back** / **Next** footer. On the **last** filter page the forward button reads **Review**.
3. **Review page** — the current editable review (removable chips, focused "Edit" jump-back to a step), primary CTA **"Find recipes."**
4. **Results page** — a dedicated page listing the ranked recipes to pick from (each → recipe detail).

**Navigation & state (recommended)**
- **URL-driven steps** so browser Back/Forward and deep links work and each step is a real page: e.g. `/app` (pantry), `/app/filters/[step]` (`cuisine|meal|diet|avoid|more|review`), `/app/results`. (A `?step=` query param is a lighter alternative.)
- Filter answers persist in a small client store (extend the existing localStorage "last-used" prefill, or a lightweight context/zustand) so **Back never loses input** and a mid-flow refresh resumes.
- Forward is guarded only where a step is genuinely required (e.g. optionally require a cuisine); most filters are optional, so **Next** stays enabled.

**Reuse — this is mostly re-composition, not new logic**
- The existing `FilterWizard` step bodies (cuisine drill-down, meal/diet/allergen/dislike pills, the review chips) become per-page components.
- `PantryManager` → the pantry page; `ResultsList` → the results page; the removable-chip review → the review page.
- A shared `useFilterAnswers` store replaces the wizard's internal `useState`.

**Polish:** directional slide transitions between steps (respect `prefers-reduced-motion`), consistent Back/Next footer, mobile-first (the paged flow suits phones better than the dense single screen). Keep the "Fresh Editorial" tokens and ingredient-token motif.

**Verification:** walk the flow forward and backward with no lost input; refresh mid-step resumes; deep-link a step; "Find recipes" → results → detail; lint/build; light + dark; 375 px.

**Effort:** ~2–3 sessions (routing + answers store + re-composing components + transitions). **No backend changes** — the pantry, filters, and recommend endpoints are unchanged; this is a frontend shell/routing rework.

---

## Phase 1 — Ratings & feedback loop (UI)  ·  small

**Why first:** the backend already has the home for this — `interaction_history` and `POST /v1/feedback` exist and are only written by the agent logging "recommended." This closes a one-way log into a real loop and is highly demoable.

**Backend**
- `POST /v1/feedback` already accepts `{user_key, recipe_id, action}`. Confirm/extend the `action` vocabulary to `{cooked, liked, disliked, saved, dismissed}` (a plain string today — add light validation).
- Add `GET /v1/feedback/{user_key}` (or fold into the profile response) returning the user's recent actions so the UI can render "Cooked"/"Saved" states. Small read over `interaction_history`.

**Frontend**
- Recipe header (`components/recipe/recipe-header.tsx`): a compact **"Made this"** toggle + thumbs up/down, wired through a new `use-feedback` mutation (mirror `use-modify-recipe`). Optimistic, toast confirmation.
- Result card (`components/results/recipe-card.tsx`): a quick save/dismiss affordance.
- A `useFeedback`/`useUserFeedback` hook + query-key; render persisted state on load.

**Verification:** click "Made this" on a recipe → row in `interaction_history`, state persists across reload; dislike a result → sinks on the next recommend (ties into Phase 3). Tests: feedback endpoint action validation; frontend lint/build.

**Effort:** ~1 focused session. No migration (table exists; add one only if `action` needs an enum/constraint).

---

## Phase 2 — Saved recipes & meal planning  ·  medium

**Why:** turns discovery into a place users return to, and makes the shopping-list feature multi-recipe. "Save" is also a Phase-1 action, so the two dovetail.

**Backend**
- Migration `0011`: `saved_recipes(user_key, recipe_id, created_at)` (unique per pair) and `meal_plans(id, user_key, name, created_at)` + `meal_plan_items(plan_id, recipe_id, slot)` (slot = free-text day/meal label).
- Endpoints: `GET/POST/DELETE /v1/saved`, `GET/POST /v1/plans`, `POST /v1/plans/{id}/items`, `DELETE /v1/plans/{id}/items/{recipe_id}`, and `GET /v1/plans/{id}/shopping-list` (reuse `services/shopping.py` over the plan's recipes minus pantry).
- Models + schemas; per-user scoping like `pantry`/`profile`.

**Frontend**
- A **Saved** list on `/app` (or a `/saved` route): saved recipe cards, remove.
- "Add to plan" action on the recipe detail + result cards.
- `/plan` view: simple day/meal slots, drag-or-tap to arrange, and a one-tap **combined shopping list** (reuses the existing shopping-list rendering).
- Hooks: `use-saved`, `use-plans`; query keys; types.

**Verification:** save a recipe → appears in Saved and survives reload; build a 3-dinner plan → combined shopping list aggregates correctly, pantry excluded. Tests: saved/plan CRUD + plan shopping-list aggregation (DB-backed, dynamic ids).

**Effort:** ~2–3 sessions (migration + 6 endpoints + 2 views). Ships incrementally: **Saved** first (leans on Phase-1 "save"), then the meal-plan layer.

---

## Phase 3 — Learned personalization  ·  medium

**Why:** the README's "preference-aware personalization from user feedback" is only half-there (explicit prefs + recency). This adds a gentle behavioral signal without a heavy ML system.

**Approach (deterministic + embeddings, no training):**
- Build a per-user **taste vector** = mean of the embeddings of recipes the user saved/cooked (positive) minus a fraction of dismissed/disliked (negative). Cheap, incremental, explainable.
- In ranking (`services/ranking.py`), add a small weighted term: cosine(taste_vector, recipe.embedding), behind a config weight, applied *after* hard filters (never overrides safety). Sinks disliked-similar, floats liked-similar.
- Cold-start: no taste vector → current behavior unchanged.

**Backend**
- Compute the taste vector on demand from `interaction_history` + `recipes.embedding` (cache per user in Redis, short TTL), or precompute in the profile.
- Ranking term + weight in `config.py`; a `why`/explanation string ("Because you liked …") when the term is decisive, kept honest.

**Frontend**
- No new UI. Optional: surface the "Because you …" reason on cards; a settings toggle to disable personalization (respect user control).

**Verification:** save several paneer dishes → paneer-ish recipes rank higher on the next recommend; dismiss a cuisine → it recedes. Extend the eval harness with a personalization scenario (synthetic history → expected reordering). Keep violations at 0.

**Effort:** ~2 sessions. Guardrails: it only *reorders within* the already-safe, already-filtered set; weight is tunable and disable-able.

---

## Phase 4 — Online analytics & A/B  ·  medium

**Why:** the architecture's "Analytics and Evaluation Pipeline" box is unbuilt — only offline evals + generation logs exist. This adds the minimal online layer to actually compare variants.

**Backend**
- Migration `0012`: `events(id, user_key, session_id, name, recipe_id, variant, props jsonb, created_at)` with an index on `(name, created_at)`.
- Deterministic **variant assignment** per session (hash of session_id → bucket) for a named experiment (e.g. `ranking_v1` vs a Phase-3 personalized variant, or `prompt_v1` vs `prompt_v2`), surfaced in the recommend response so the frontend can log outcomes against it.
- `POST /v1/events` (view/open/cook/save/time-to-answer) and `GET /v1/experiments/{name}/summary` (per-variant counts + conversion rates).
- Reuse the offline eval definitions so online/offline metrics stay comparable.

**Frontend**
- A tiny `track(name, props)` helper posting to `/v1/events` at key moments (results shown, recipe opened, cooked, saved), tagged with the response's `variant`.

**Verification:** two sessions land in different buckets; the summary endpoint shows per-variant open/cook rates; an offline eval reproduces the same metric on gold data. Tests: deterministic bucketing, event insert, summary aggregation.

**Effort:** ~2 sessions. Start with **event capture + summary** (immediately useful), add **variant assignment** once there's a second thing to compare (pairs naturally with Phase 3).

---

## Phase 5 — Observability surface  ·  small–medium

**Why:** rich data is already logged (`generation_events`: model/prompt_version/violations/repaired/degraded/latency_ms/tokens; `agent_traces`; cache metrics) but there's no way to *see* it.

**Backend**
- `GET /v1/admin/metrics` (admin-gated): rolled-up latency (p50/p95), LLM cost & token usage, degraded/repair rates, constraint-violation counts, cache hit-rate — aggregated from the existing tables. Read-only, cheap.
- Optionally emit the same as Prometheus-format text for Grafana.

**Frontend**
- A minimal admin-only page (charts from the JSON, or just tables) — or skip the UI and rely on the endpoint + Grafana.

**Verification:** run a few agent/recommend calls → the endpoint reflects the new events (latency, cost, degraded count). Test: aggregation query over seeded `generation_events`.

**Effort:** ~1–2 sessions. No new data model — it's a read/aggregate layer over what's already captured.

---

## Phase 6 — Complete the MCP tool surface  ·  small

**Why:** the README advertises `check_inventory` and `save_meal_plan` as MCP tools; the registry has 5 others. Adding these makes the pantry readable and a plan writable by agent/MCP clients — the "action-oriented output" the project is about.

**Backend**
- `app/agent/tools.py`: add `check_inventory(user_key)` → the user's pantry (reuse `services/pantry`), and `save_meal_plan(user_key, name, recipe_ids)` → persist via Phase-2's `meal_plans` (depends on Phase 2). Each stays deterministic — no LLM inside — per the tool-layer fence.
- They auto-expose over MCP (`app/mcp_server.py` renders all `TOOLS`) and are usable by the single-agent loop and the LangGraph orchestrator.

**Verification:** `make mcp-verify` lists 7 tools; `check_inventory` returns the pantry; `save_meal_plan` writes a plan row. Tests: tool dispatch + DB effect (mocked/`@requires_db`).

**Effort:** ~1 session. **Depends on Phase 2** for the meal-plan store (`check_inventory` can land independently earlier).

---

## Suggested sequence

`UX Redesign (paged flow)` → `Phase 1 (feedback UI)` → `Phase 2 (saved + plans)` → `Phase 6 (MCP tools, once plans exist)` → `Phase 3 (personalization)` → `Phase 4 (analytics/A-B)` → `Phase 5 (observability)`.

The paged-flow redesign comes first (or alongside Phase 1) because it defines the pages the feature work then lands on — ratings on the results/detail pages, "Save" and "Add to plan" as actions in the new flow. Phases 1–2 are the most user-visible and unlock the rest (save/cook signals feed Phase 3; plans back Phase 6). Phases 3–5 are the "make it smart and measurable" layer and can be interleaved. Each phase is independently shippable with its own demo, and none regress the deterministic-first, fail-open guarantees the app already holds.
