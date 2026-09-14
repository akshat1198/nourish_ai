"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, ShieldCheck, ShoppingBasket } from "lucide-react";
import type { PlannerResponse } from "@/types/api";

/** Shopping list comes back as an open-ended dict; render whatever shape it has
 *  without inventing structure the backend did not promise. */
function shoppingItems(list: Record<string, unknown>): string[] {
  const raw = (list?.items ?? list?.missing ?? []) as unknown;
  if (Array.isArray(raw)) {
    return raw
      .map((i) => (typeof i === "string" ? i : ((i as Record<string, unknown>)?.name as string)))
      .filter(Boolean);
  }
  return Object.keys(list ?? {});
}

export function PlannerResult({ data }: { data: PlannerResponse }) {
  const recipes = data.plan?.recipes ?? [];
  const items = shoppingItems(data.shopping_list);

  if (!recipes.length) {
    return (
      <div className="rounded-xl border border-border bg-card p-6 text-center">
        <p className="font-medium">No plan this time.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          Try naming a cuisine or loosening a constraint, then ask again.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Degraded means the validator could not clear a model-written plan and
          the deterministic fallback answered instead. Say so -- the difference
          matters to anyone reading the reasoning below as if a model wrote it. */}
      {data.degraded && (
        <p className="flex items-start gap-2 rounded-lg border border-[var(--turmeric)]/40 bg-[var(--accent)] px-3 py-2 text-sm text-[var(--accent-foreground)]">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          Built from a safe fallback rather than the planner, so the notes below
          are briefer than usual.
        </p>
      )}

      {/* What was enforced in SQL, not what the model was asked for. Shown
          because the matcher is deliberately conservative: a phrasing it does
          not recognise must not read as a promise that it was applied. */}
      {(data.applied_constraints?.exclude_allergens?.length > 0 ||
        data.applied_constraints?.diet) && (
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5 text-[var(--curry-leaf)]" aria-hidden />
          Excluded from every result:
          {data.applied_constraints.diet && (
            <span className="rounded-full bg-[var(--curry-leaf)]/10 px-2 py-0.5 font-medium text-[var(--curry-leaf)]">
              {data.applied_constraints.diet.replace("_", "-")}
            </span>
          )}
          {data.applied_constraints.exclude_allergens.map((a) => (
            <span
              key={a}
              className="rounded-full bg-[var(--curry-leaf)]/10 px-2 py-0.5 font-medium text-[var(--curry-leaf)]"
            >
              no {a}
            </span>
          ))}
        </p>
      )}

      {data.plan?.summary && (
        <p className="font-serif text-lg leading-relaxed text-balance">{data.plan.summary}</p>
      )}

      <ul className="space-y-3">
        {recipes.map((r) => (
          <li key={r.recipe_id}>
            <Link
              href={`/recipes/${r.recipe_id}`}
              className="group block rounded-xl border border-border bg-card p-4 transition-colors hover:border-[var(--curry-leaf)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-serif text-lg leading-snug">{r.title}</h3>
                <ArrowRight
                  className="mt-1 size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{r.why}</p>
            </Link>
          </li>
        ))}
      </ul>

      {items.length > 0 && (
        <section className="rounded-xl border border-border bg-secondary/50 p-4">
          <h4 className="flex items-center gap-2 text-sm font-semibold">
            <ShoppingBasket className="size-4 text-[var(--curry-leaf)]" aria-hidden />
            Still need to buy
          </h4>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {items.map((item) => (
              <li
                key={item}
                className="rounded-full border border-border bg-card px-2.5 py-1 text-xs"
              >
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
