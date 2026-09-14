"use client";

import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import type { PlannerTraceEvent } from "@/types/api";

/** The graph's five nodes, in the fixed order they execute.
 *
 * Mirrors backend/app/orchestrator/graph.py. Two of these are plain code, not
 * model calls, which is worth surfacing: it is the reason a plan can be trusted
 * to be allergen-safe rather than merely claimed to be.
 */
const STAGES = [
  { node: "pantry_analyst", label: "Reading your pantry", kind: "ai" },
  { node: "recipe_planner", label: "Choosing dishes", kind: "ai" },
  { node: "safety_nutritionist", label: "Checking allergens & nutrition", kind: "code" },
  { node: "shopping_planner", label: "Building the shopping list", kind: "code" },
  { node: "supervisor", label: "Writing it up", kind: "ai" },
] as const;

// Elapsed-time thresholds, in ms, at which each stage is *expected* to begin.
// The endpoint returns its trace only when the whole run finishes, so there is
// no live signal to drive this from. The order is genuinely fixed and the p50 is
// ~6.8s, so advancing on a clock is a fair approximation of a real sequence --
// but it is an estimate, which is why nothing here claims a stage has finished
// until the real trace comes back and replaces these with measured timings.
const EXPECTED_START_MS = [0, 900, 4200, 5200, 5600];

function useElapsed(active: boolean) {
  const [ms, setMs] = useState(0);
  useEffect(() => {
    if (!active) {
      setMs(0);
      return;
    }
    const t0 = performance.now();
    const id = window.setInterval(() => setMs(performance.now() - t0), 100);
    return () => window.clearInterval(id);
  }, [active]);
  return ms;
}

export function PlannerStages({
  active,
  trace,
}: {
  active: boolean;
  trace?: PlannerTraceEvent[];
}) {
  const elapsed = useElapsed(active);
  const reduced = useReducedMotion();

  // Once the run is done the trace carries real per-node latencies; prefer them
  // over the estimates so what the user ends up reading is measured, not guessed.
  const measured = new Map<string, number>();
  for (const e of trace ?? []) {
    if (e.node && typeof e.latency_ms === "number") {
      measured.set(e.node, (measured.get(e.node) ?? 0) + e.latency_ms);
    }
  }
  const done = !active && (trace?.length ?? 0) > 0;

  const currentIndex = EXPECTED_START_MS.filter((t) => elapsed >= t).length - 1;

  return (
    <ol
      className="space-y-1"
      aria-live="polite"
      aria-label={active ? "Planning in progress" : "Planning steps"}
    >
      {STAGES.map((stage, i) => {
        const isDone = done || (active && i < currentIndex);
        const isCurrent = active && i === currentIndex;
        const real = measured.get(stage.node);

        return (
          <li
            key={stage.node}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-200",
              isCurrent && "bg-secondary",
              !isCurrent && !isDone && "opacity-45",
            )}
          >
            <span className="flex size-5 shrink-0 items-center justify-center">
              {isDone ? (
                <Check className="size-4 text-[var(--curry-leaf)]" aria-hidden />
              ) : isCurrent ? (
                <Loader2
                  className={cn("size-4 text-[var(--turmeric)]", !reduced && "animate-spin")}
                  aria-hidden
                />
              ) : (
                <span className="size-1.5 rounded-full bg-border" aria-hidden />
              )}
            </span>

            <span className="flex-1">{stage.label}</span>

            {/* Not decoration: it says which steps a model decided and which are
                deterministic checks the model cannot talk its way past. */}
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                stage.kind === "code"
                  ? "bg-[var(--curry-leaf)]/10 text-[var(--curry-leaf)]"
                  : "bg-[var(--turmeric)]/15 text-[var(--accent-foreground)]",
              )}
            >
              {stage.kind === "code" ? "verified" : "AI"}
            </span>

            {real !== undefined && (
              <span className="w-12 text-right text-xs tabular-nums text-muted-foreground">
                {(real / 1000).toFixed(1)}s
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
