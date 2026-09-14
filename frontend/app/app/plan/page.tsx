"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PlannerResult } from "@/components/planner/planner-result";
import { PlannerStages } from "@/components/planner/planner-stages";
import { getPlannerSessionId, usePlanner } from "@/lib/hooks/use-planner";
import { usePantry } from "@/lib/hooks/use-pantry";
import { ApiError } from "@/lib/api";

const EXAMPLES = [
  "Something high-protein tonight, no dairy",
  "Two quick vegetarian dinners for this week",
  "I'm bored of chicken — surprise me",
];

export default function PlanPage() {
  const [question, setQuestion] = useState("");
  const pantry = usePantry();
  const planner = usePlanner();

  const pantryNames = (pantry.data?.items ?? []).map((i) => i.ingredient);
  const canAsk = question.trim().length > 2 && !planner.isPending;

  function ask(q: string) {
    const text = q.trim();
    if (!text) return;
    setQuestion(text);
    planner.mutate({
      pantry: pantryNames,
      question: text,
      session_id: getPlannerSessionId(),
      limit: 3,
    });
  }

  const err = planner.error as ApiError | Error | null;
  const status = err instanceof ApiError ? err.status : undefined;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-serif text-2xl">Ask the planner</h1>
        <p className="text-sm text-muted-foreground">
          Describe what you feel like. It reads your pantry, picks dishes, checks
          them against your diet, and writes the shopping list.
        </p>
      </header>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="space-y-3"
      >
        <label htmlFor="planner-question" className="block text-sm font-medium">
          What do you feel like?
        </label>
        <textarea
          id="planner-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder="Something high-protein tonight, no dairy…"
          className="w-full resize-none rounded-xl border border-input bg-card px-3.5 py-3 text-base leading-relaxed outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-[var(--curry-leaf)] focus-visible:ring-2 focus-visible:ring-ring"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) ask(question);
          }}
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" disabled={!canAsk} className="min-h-11">
            <Sparkles className="size-4" aria-hidden />
            {planner.isPending ? "Planning…" : "Ask"}
          </Button>
          <p className="text-xs text-muted-foreground">
            {pantryNames.length > 0
              ? `Using ${pantryNames.length} pantry ${pantryNames.length === 1 ? "item" : "items"}`
              : "Your pantry is empty — it will suggest from scratch"}
          </p>
        </div>

        {!planner.isPending && !planner.data && (
          <ul className="flex flex-wrap gap-2 pt-1">
            {EXAMPLES.map((ex) => (
              <li key={ex}>
                <button
                  type="button"
                  onClick={() => ask(ex)}
                  className="min-h-9 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-[var(--curry-leaf)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {ex}
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>

      {/* Stages stay mounted after the run so the measured per-node timings
          replace the estimates in place, rather than vanishing on completion. */}
      {(planner.isPending || planner.data) && (
        <section className="rounded-xl border border-border bg-card p-3">
          <PlannerStages active={planner.isPending} trace={planner.data?.trace} />
          {planner.isPending && (
            <p className="px-3 pt-2 text-xs text-muted-foreground">
              Usually about 7 seconds.
            </p>
          )}
        </section>
      )}

      {err && (
        <div
          role="alert"
          className="space-y-2 rounded-xl border border-[var(--chili)]/40 bg-[var(--chili)]/5 p-4 text-sm"
        >
          <p className="font-medium">
            {status === 429
              ? "You've used today's planning requests."
              : status === 401
                ? "Sign in to use the planner."
                : status === 503
                  ? "The planner is unavailable right now."
                  : "That didn't go through."}
          </p>
          <p className="text-muted-foreground">
            {status === 429
              ? "The quota resets at midnight UTC. Regular search still works in the meantime."
              : status === 503
                ? "Regular search still works — try the planner again shortly."
                : (err instanceof ApiError ? err.detail : err.message) || "Please try again."}
          </p>
          {status !== 429 && status !== 401 && (
            <Button variant="outline" className="min-h-11" onClick={() => ask(question)}>
              Try again
            </Button>
          )}
        </div>
      )}

      {planner.data && <PlannerResult data={planner.data} />}
    </div>
  );
}
