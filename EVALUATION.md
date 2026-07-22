# NourishAI — Evaluation: Single Agent vs. Multi-Agent Graph

How the two orchestration strategies were compared, what was measured, the
results, and the honest limitations of the test set.

## 1. What is being compared

Both engines answer the same question — *"given this pantry and these
constraints, recommend safe, relevant recipes"* — over the **same tools and the
same database**. Only the orchestration differs:

| | **Single agent** | **Multi-agent graph** |
|---|---|---|
| Mechanic | Raw Anthropic tool-calling loop (`while stop_reason == "tool_use"`) | LangGraph supervisor + specialist nodes |
| Who chooses tools | The LLM, open-ended, over multiple turns | A fixed pipeline: pantry → planner → safety → shopping → summary |
| LLM's job | Decide which tools to call, when to stop, then produce a plan | Pick from a pre-filtered shortlist + write the final summary |
| Shared | Same 5 tools, same retrieval, **same deterministic validator** | Same 5 tools, same retrieval, **same deterministic validator** |

Because the tools, data, and validator are held constant, the **only variable is
the orchestration approach** — that is what makes this a fair A/B rather than two
unrelated demos.

## 2. The test set — 30 cases

Source: `backend/seed_data/eval/queries.jsonl`. Each case is a realistic pantry
plus optional hard constraints and a set of known-relevant recipes:

```json
{"name": "tofu stir-fry vegan quick", "pantry": ["tofu","green beans","garlic","ginger","soy sauce","rice"],
 "diet": "vegan", "max_time_minutes": 30, "relevant_titles": ["Tofu & Green Beans Stir-Fry"]}
```

**Composition (deliberate spread):**
- **30 cases**, pantries of 4–7 ingredients.
- **Cuisine/protein diversity:** Italian, Greek, Indian, Thai, Mexican, Japanese,
  Middle-Eastern; chicken, beef, tofu, lentils, chickpeas, kidney beans, paneer,
  salmon, cod, prawns, eggs.
- **Constraint coverage:** 7 diet-restricted (6 vegan, 1 vegetarian),
  1 allergen-exclusion (nut-free), 4 time-limited (15–30 min). The rest are
  unconstrained "what can I cook with this" queries.
- **Normalization stressors:** cases deliberately use ingredient *aliases* to
  test the canonicalization layer — `prawns→shrimp`, `courgette→zucchini`,
  `scallion→green onion`. A recommender that matched on raw strings would miss
  these; these cases prove the alias/normalization path works end-to-end.

**Why these are good cases:** they are hand-vetted (each has a known-correct
target recipe), they exercise every hard constraint the product promises
(diet / allergen / time), and they cover the ingredient-matching edge cases that
break naïve retrieval. They were first built for the **retrieval** eval
(hit@5 / hit@10 / MRR) and reused here so the agent comparison rides on a
retrieval layer whose quality was already measured separately.

**What the gold set does NOT cover — and how it's addressed:**
- **The gold cases are "easy":** structured queries with clear-cut, satisfiable
  constraints. That is why their constraint pass-rate is a perfect 1.00 — it is a
  *floor* check ("never ships a violation"), not a hard discriminator.
- **The gold set alone never fires the repair/fallback path.** Because retrieval
  hard-filters diet/allergen/time before the LLM sees candidates, the model rarely
  picks a violating recipe. **This gap is now closed by a second suite** — the
  *adversarial* set (§2b) — which forces the repair loop with real API calls; the
  recovery logic is *also* unit-tested (`test_agent_loop.py`,
  `test_orchestrator.py`) with forced-violation fakes.
- **Thin constraint stress:** only 1 allergen case and 4 time-limited cases in the
  gold set.
- **No free-text pantry** cases in the comparison (pantries are structured lists,
  so the free-text parsing model isn't in the loop here) — see §7.

## 2b. The adversarial suite — forcing the repair loop

Source: `backend/seed_data/eval/queries_adversarial.jsonl`, run with
`--suite adversarial`. These exist to exercise the one path the gold set can't:
**corrective repair and graceful degradation.**

**The mechanism (why they reliably trigger it):** retrieval hard-filters
diet/allergen/time, but it does **not** filter `disliked_ingredients` — yet the
validator *does* (`validator.py`). So a pantry whose best matches are dominated by
a disliked ingredient surfaces violating candidates the retrieval layer can't
remove. `garlic` appears in **105 of 144 recipes**, so a savory pantry + "dislike
garlic" leaves the model few clean options — it must either pick a violating recipe
(→ validator flags it → repair turn) or fail to find a clean plan (→ degraded
fallback). Each of the 6 cases is a preference-conflict of this shape (garlic /
onion / scallion), from "recoverable" to "near-unsatisfiable."

**Safety note & the dislike tier:** allergen/diet/time are *hard* constraints —
hard-filtered by retrieval, so no plan (agent or fallback) can violate them. A
disliked ingredient is a *soft* preference, handled in tiers: the agent tries hard
to honor it (a violation drives a repair turn), and if it must fall back, the
deterministic fallback **demotes** disliked recipes in ranking
(`RANK_W_DISLIKE`) so they sink beneath every clean option and surface *only* if
nothing clean fits. So a degraded plan is always safe *and* honors the dislike
whenever the corpus allows — it silently ships neither a hard violation nor an
avoidable disliked ingredient.

## 3. How to run it

```bash
# 2-case dry run first — prints projected full-run cost (spends real tokens)
python -m app.evals.run_agent --engine both

# full comparison (cost-gated: >3 cases requires --yes)
python -m app.evals.run_agent --engine both --limit 30 --yes

# adversarial suite — forces the repair/degraded path
python -m app.evals.run_agent --suite adversarial --engine both --limit 6 --yes -v
```

`--engine single | graph | both`, `--suite gold | adversarial`. One harness, two
switches, the same cases through
each engine, then a side-by-side table. It hits the real Anthropic API, so it is
capped at 30 cases and requires `--yes` beyond 3 (a full run is always
deliberate).

## 4. Metrics — what each one is and how it's measured

| Metric | Definition | How it's measured |
|---|---|---|
| **Constraint pass-rate** | % of cases producing a **validator-clean plan on the first attempt** (no repair, no fallback) | A deterministic Python validator re-queries the DB per plan (see §5). "Pass" = zero violations before any repair turn. |
| **Repair-success rate** | Of runs that needed a repair turn, how many ended clean | Loop/graph flag a run as repaired; validator re-checks the corrected plan. |
| **Degraded rate** | % that fell back to the deterministic default plan | Set when repairs are exhausted or structured output can't be produced. |
| **Mean tool calls** | Avg tool invocations per case (single engine only) | Counted in the loop; the graph's tool use is fixed by its topology. |
| **p50 latency** | Median wall-clock seconds per case | `time.perf_counter()` around each case; median over 30. |
| **Tokens in / out** | Summed prompt + completion tokens across the run | Single: from the Anthropic SDK `usage` on every call. Graph: aggregated via langchain's `get_usage_metadata_callback` across all model calls in a run. |
| **Estimated cost** | Tokens × model price | Sonnet-5 pricing ($3 / 1M input, $15 / 1M output). |

### Why these five dimensions
- **Correctness** (pass-rate, degraded) — does it obey the hard promises.
- **Reliability** (repair/degraded) — how often the happy path fails and whether it recovers safely.
- **Efficiency** (tokens) — the true cost driver.
- **Latency** (p50) — user-facing speed.
- **Price** ($) — the bottom line, derived from tokens.

## 5. How correctness is *actually* ensured (the credibility anchor)

Pass-rate is **not** the model grading itself. Every plan — from either engine —
is checked by a deterministic validator (`app/agent/validator.py`) that
**re-queries the database**, not the model's claims:

- every recommended recipe exists,
- contains **no excluded allergen**,
- matches the requested **diet**,
- fits the **time limit**,
- contains no **disliked ingredient** (alias-normalized).

The same validator backs both engines and also drives the repair loop, so a
"pass" means the identical thing on both sides. This is a deliberate design
choice: **an LLM is never in the validation hot path** — using a model to check a
model would reintroduce the exact failure mode being checked.

## 6. Results — full 30-case run (2026-07-13, `claude-sonnet-5`)

| metric | single agent | graph | 
|---|--:|--:|
| **constraint pass-rate (1st try)** | 1.00 (30/30) | 1.00 (30/30) |
| **degraded** | 0/30 | 0/30 |
| **p50 latency** | 18.1 s | **6.8 s** |
| **tokens in / out** | 210,374 / 24,809 | **35,074 / 6,863** |
| **estimated cost** | $1.003 | **$0.208** |

**Read:** correctness identical; the graph is **~4.8× cheaper** and **~2.7×
faster**.

### 6b. Adversarial run (6 preference-conflict cases, `--suite adversarial`)

Here a *low* first-try pass-rate is the goal — these cases are built to be
unsatisfiable-or-hard, so the interesting metrics are repair-success and
degraded-rate (does the safety path fire and stay safe), not pass-rate.

| metric | single agent | graph |
|---|--:|--:|
| **clean 1st try** | 0/6 | 1/6 |
| **repair-success** (of those repaired) | **2/6** | 0/5 |
| **degraded (safe fallback)** | 4/6 | 5/6 |
| **mean tool calls** | 3.3 (vs 1.5 gold) | — |
| **p50 latency** | 50.5 s | 13.4 s |
| **est. cost** | $0.549 | $0.100 |

**Read:** the repair loop and the degraded fallback **both fire on both engines** —
the gap the gold set couldn't cover is now exercised against the live API. Two
observations worth their own line:
- **Every final answer stayed safe.** Degraded cases still honor diet/allergen/time;
  they just couldn't fully honor the *preference* (a soft constraint) — by design.
- **The single agent recovered where the graph didn't** (repaired-to-clean 2/6 vs
  0/5). Its open-ended flexibility — re-searching, reasoning around the conflict —
  is exactly what the graph's fixed pipeline lacks. Small sample and stochastic, but
  it's the concrete argument for *keeping* the flexible agent for hard/open inputs
  even though the graph wins on well-shaped ones (§7).
- The **timeout fix showed up live**: one case's structuring call stalled, failed
  fast at 20 s, and *degraded safely* instead of hanging the run.

## 6c. Retrieval re-baseline at corpus scale

The corpus grew **52×**: 144 seed → **7,580 recipes** (+708 TheMealDB, +6,728
Archana's Kitchen with regional Indian cuisine). All 7,580 embedded (MiniLM-L6,
HNSW). Re-ran `run_retrieval --mode both` on three gold sets:

| Gold set | SQL hit@5 | Hybrid hit@5 | violations |
|---|---|---|---|
| structured (`queries.jsonl`, 30) | 1.00 | 1.00 | 0 |
| **regional-Indian** (`queries_regional.jsonl`, 8, NEW) | 0.875 | **1.00** | 0 |
| fuzzy (`fuzzy_queries.jsonl`, 8) | 0.125 | 0.75 | 0 |

- **Structured holds at 52× scale** — the original gold recipes still rank top-5
  against 7,436 new competitors. hit@5 stays 1.0 (SQL MRR softens 1.0→0.84 as
  near-duplicates crowd in, but the target never leaves top-5).
- **Regional set is where hybrid earns its keep**: SQL drops Kerala avial (returns
  a different vegetable poriyal); hybrid's vector arm surfaces the actual avial at
  #1. New cases are built from a real regional dish's own ingredients + its
  `cuisines`/`meal_type` filter (the eval harness gained those fields in 6.3).
- **Fuzzy hybrid fell 1.0 → 0.75 at scale** — the plan's "vector noise at scale"
  tripwire. Investigated per the plan: sweeping `RRF_POOL` 30→200 left it
  **unchanged at 0.75**, so it is *not* a candidate-pool artifact — it's genuine
  competition (those cases were authored to hit specific *seed* recipes that now
  compete with 7,400 others; some misses are plausibly better matches to new
  recipes). Hybrid still beats SQL **6×**. Not "fixed" by tuning; recorded honestly.
- **violations = 0 on every set** — cuisine/region/meal/diet/allergen filters all
  hold post-fusion; the bigger corpus introduced no constraint leakage.

## 7. Interpretation

- **Correctness parity was expected** — both engines are bounded by the same
  deterministic validator, so neither can ship a constraint violation. On this
  set the pass-rate is a floor check, and both clear it.
- **The cost/latency gap was the finding — and it contradicted the going-in
  hypothesis.** The expectation was that the multi-agent graph, being more
  elaborate, would cost *more*. It's the opposite: the single agent re-sends the
  full tool schemas and accumulates extended-thinking on **every** turn of its
  loop (210k input tokens); the graph replaces open-ended tool-choosing with a
  deterministic pipeline and spends the LLM only where it adds value — picking
  from a code-pre-filtered shortlist and writing the summary (35k tokens).
- **The point of the exercise was to measure that tradeoff rather than assume
  it.** The measurement flipped the intuition, which is exactly why it was worth
  running.
- **On hard inputs the tradeoff reverses (§6b).** The adversarial suite shows the
  single agent recovering from preference-conflicts the graph degrades on — the
  flexibility that costs tokens on easy cases earns them back on hard ones. The
  honest takeaway is *not* "graph wins," it's "match the engine to the input:
  pipeline for well-shaped tasks, flexible agent for open-ended/conflicting ones."

### What I'd add next to make the set discriminating
1. ~~Adversarial / conflicting-constraint cases~~ — **done** (§2b): the adversarial
   suite forces the repair and degraded-fallback paths against the live API.
2. **Free-text pantry** cases ("half a bag of spinach and some leftover
   chicken") to bring the parsing model into the comparison.
3. **More allergen and time stress** — the gold set has only 1 and 4.
4. **A larger adversarial set** — 6 cases show the paths fire but are too few and
   too stochastic to *rank* the engines on recovery; 20–30 would.
5. **An LLM-judge pass (opus) for answer *quality*** (not correctness) — is the
   `why`/summary genuinely helpful — kept off by default because it costs money
   and correctness is already covered deterministically.

## 8. Reproducibility notes

- Deterministic where it can be: retrieval, ranking, validation, and shopping-list
  aggregation are pure code; only the recipe pick and the summary are LLM calls.
- The API is non-deterministic, so absolute latencies vary run to run; the
  **relative** single-vs-graph gap is stable and large enough to be the signal.
- Cost is an over-estimate (standard Sonnet-5 pricing; introductory rates are
  lower), and LLM calls are bounded by a timeout + retry cap so a stalled request
  fails fast rather than hanging a run.

## 9. Anticipated questions

Honest answers to the questions this evaluation invites. Kept here so the doc
pre-empts them rather than hiding from them.

### Test design

**What kinds of tests are in the 30 cases?**
End-to-end recommendation cases: a realistic pantry of 4–7 ingredients plus
optional hard constraints, each with a known-correct target recipe. Spread across
cuisines and proteins (Italian, Thai, Indian, Mexican, Japanese, Middle-Eastern;
chicken, beef, tofu, lentils, chickpeas, paneer, salmon, cod, prawns). Constraint
coverage: 7 diet-restricted (6 vegan, 1 vegetarian), 1 allergen-exclusion
(nut-free), 4 time-limited (15–30 min), rest unconstrained. Several use ingredient
*aliases* (prawns, courgette, scallion) so they only pass if canonicalization
works, not exact string match.

**How holistic were they, really?**
Holistic on breadth, thin on difficulty — stated upfront. The gold set covers every
hard constraint the product promises and the ingredient-matching edge cases, on top
of a retrieval layer measured separately (hit@5/MRR). But they're "easy":
structured, satisfiable queries, which is why gold pass-rate is a perfect 1.00 — a
floor check, not a discriminator. The gold set alone never fires the repair/fallback
path (retrieval pre-filters candidates) — so a *second* adversarial suite (§2b)
forces it with real API calls (via disliked ingredients retrieval can't filter),
and it's also unit-tested with forced violations. Together the two suites cover both
the happy path and the recovery path.

**Why were these good cases — what was considered?**
(1) Hand-vetted with a known-correct answer, so "right or wrong" is objective, not
a judgment call. (2) They exercise every promise — diet, allergen, time — not just
happy-path lookups. (3) They include the failure modes that break naïve
recommenders (aliases, near-miss names). (4) Reused from the retrieval eval, so the
agent comparison inherits a retrieval layer whose quality was already quantified.

### Harder questions

**Isn't 30 cases too few to be statistically significant?**
For a precise correctness rate, yes — and that claim isn't made. What 30 diverse,
hand-vetted cases *do* support: (1) a floor check — neither engine shipped a single
violation, backed by a fail-closed validator whose guarantee is structural, not
sampled; (2) the efficiency finding, where the effect is ~5× on tokens and ~2.7× on
latency, same direction on every case. A paired comparison with a 5× gap is
convincing at n=30; a 3% gap would not be. Ranking engines on correctness would
need a larger, harder set — showing "dramatically cheaper for equal correctness"
does not.

**A perfect 1.00 pass-rate — isn't that a red flag the eval is useless?**
An unexplained 1.00 would be. This one is explained: retrieval hard-filters diet,
allergen, and time *before* the model sees candidates, so the LLM picks from an
already-safe set and a violation would take active off-script behavior. So 1.00 is
expected — it shows the guardrails work, not that the model is flawless. It does
*not* discriminate the engines on quality, which is why the interesting result on
the gold set is cost/latency. And it's precisely why the adversarial suite (§2b, §6b)
exists — there the safe set is deliberately starved, first-try pass-rate drops to
0–1/6, and the repair/degraded metrics become the discriminating signal.

**Why not just use an LLM-as-judge?**
A judge is used for the right thing and avoided for the wrong thing. For
*correctness* (did this violate a diet/allergen), a deterministic DB validator is
strictly better — cheaper, faster, and it can't be wrong about whether a recipe
contains nuts; an LLM judge would check a model with a model. A judge earns its
keep on *subjective quality* (is the explanation/summary helpful), which no
validator can score — so an optional opus judge exists, off by default, for quality
only.

**The graph is cheaper and just as correct — so kill the single agent?**
Not yet, and the eval is why that can be said carefully. The graph wins *on this
workload* — structured pantries, well-specified constraints, a pipeline-shaped
task. The single agent's cost is its flexibility (open-ended tool selection over
many turns), which is dead weight here but is what you want on genuinely open-ended
requests the pipeline wasn't designed for. Conclusion: the multi-agent structure
isn't paying its complexity cost *on well-shaped problems*; reserve the open-ended
agent for open-ended inputs. And the adversarial suite (§6b) gives that claim teeth:
on preference-conflict cases the single agent recovered where the graph degraded
(2/6 vs 0/5) — the flexibility earns its keep exactly where the pipeline is rigid.

**How do you know the graph won't regress on harder inputs?**
The gold set covers the happy path; the adversarial suite (§6b) probes harder ones.
Safety doesn't regress by construction: retrieval hard-filters and the validator is
fail-closed, so even a degraded fallback returns a diet/allergen/time-safe recipe —
structural, not sampled, and the adversarial run confirmed every final answer stayed
safe. What the adversarial run *did* expose is a quality/recovery gap: the graph's
rigid pipeline degraded on conflicts the flexible single agent reasoned around
(0/5 vs 2/6 recovered). Honest position: safety robust to harder inputs; recovery
now measured (not just unit-tested) and shown to favor the single agent — but on a
6-case sample too small to rank definitively, so a larger adversarial set is the
next step (§7).

**Did you count tokens fairly for both engines?**
Fair for this set. Both engines get the same structured pantry input, and every LLM
call is captured — SDK `usage` for the single agent, LangChain's usage callback for
the graph. The one asymmetry: the graph's free-text pantry-parsing step runs on a
cheaper model via the raw SDK, which the callback wouldn't capture — but it doesn't
fire here because pantries are structured lists. Adding free-text cases would
require instrumenting that one call, expected to add a small amount to the graph
side.

**The API is non-deterministic — how can one run be trusted?**
The *direction and magnitude* are trusted, not the absolute numbers. Most of the
pipeline is deterministic (retrieval, ranking, validation, shopping-list); only the
recipe pick and summary are model calls, so variance is confined to two steps. The
claimed gap is 5× / 2.7×, which swamps per-run jitter. A small gap would warrant
multiple runs with mean and spread; a gap this large on a paired comparison is fair
from one clean 30-case run. Latency is flagged as the softest number, being the
most environment-sensitive.

**What surprised you?**
The hypothesis was wrong, and the data was allowed to say so. The going-in
assumption was that the more elaborate multi-agent graph would cost *more*; it came
out ~5× cheaper. The single agent re-sends its full tool schemas and accumulates
extended-thinking every loop turn (210k input tokens); the graph confines the LLM
to picking from a pre-filtered shortlist and writing the summary (35k). Building the
comparison instead of asserting "multi-agent is better" is what caught this — and it
also surfaced a real bug: the first full run hung 24 minutes because the graph's LLM
calls had no timeout, since fixed at the root.
