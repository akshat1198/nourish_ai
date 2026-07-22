"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { ArrowLeft, ShoppingCart, X } from "lucide-react";
import { SummaryCard } from "@/components/recipe/summary-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  usePlan,
  usePlanShoppingList,
  useRemovePlanItem,
} from "@/lib/hooks/use-plans";
import type { PlanItem } from "@/types/api";

const UNSCHEDULED = "Unscheduled";

export default function PlanDetailPage() {
  const params = useParams();
  const raw = Array.isArray(params.id) ? params.id[0] : params.id;
  const id = Number(raw);
  if (!Number.isInteger(id)) notFound();

  const { data: plan, isLoading, isError, error } = usePlan(id);
  const removeItem = useRemovePlanItem(id);
  const [showShopping, setShowShopping] = useState(false);
  const shopping = usePlanShoppingList(id, showShopping);

  // Group items by slot label, preserving first-seen order.
  const groups = useMemo(() => {
    const map = new Map<string, PlanItem[]>();
    for (const it of plan?.items ?? []) {
      const key = it.slot?.trim() || UNSCHEDULED;
      (map.get(key) ?? map.set(key, []).get(key)!).push(it);
    }
    return [...map.entries()];
  }, [plan]);

  if (isError && error instanceof ApiError && error.status === 404) notFound();

  return (
    <div className="space-y-6">
      <Link
        href="/app/plans"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> All plans
      </Link>

      {isLoading ? (
        <Skeleton className="h-10 w-1/2 rounded-lg" />
      ) : (
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="font-display text-4xl font-semibold tracking-tight">
            {plan?.name}
          </h1>
          {(plan?.items.length ?? 0) > 0 && (
            <Button
              variant="outline"
              className="gap-1.5"
              onClick={() => setShowShopping((s) => !s)}
            >
              <ShoppingCart className="size-4" />
              {showShopping ? "Hide shopping list" : "Shopping list"}
            </Button>
          )}
        </div>
      )}

      {showShopping && (
        <Card className="p-5">
          <h2 className="font-display text-lg font-semibold">
            Combined shopping list
          </h2>
          <p className="mb-3 text-sm text-muted-foreground">
            Everything these recipes need, minus what&apos;s in your pantry.
          </p>
          {shopping.isLoading && <Skeleton className="h-24 w-full rounded-lg" />}
          {shopping.data && shopping.data.items.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Your pantry already covers this plan. Nothing to buy.
            </p>
          )}
          {shopping.data && shopping.data.items.length > 0 && (
            <ul className="divide-y divide-border">
              {shopping.data.items.map((it) => (
                <li
                  key={`${it.name}-${it.unit ?? ""}`}
                  className="flex items-baseline justify-between gap-3 py-2 text-sm"
                >
                  <span className="capitalize">{it.name}</span>
                  <span className="tabular text-muted-foreground">
                    {it.total_qty != null
                      ? `${it.total_qty}${it.unit ? ` ${it.unit}` : ""}`
                      : it.unit ?? "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {!isLoading && plan && plan.items.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-12 text-center text-sm text-muted-foreground">
          No recipes yet. Open any recipe and use “Add to plan.”
        </div>
      )}

      {groups.map(([slot, items]) => (
        <section key={slot} className="space-y-2">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {slot}
          </h2>
          <div className="space-y-2">
            {items.map((it) => (
              <SummaryCard
                key={it.recipe.id}
                recipe={it.recipe}
                action={
                  <button
                    type="button"
                    onClick={() => removeItem.mutate(it.recipe.id)}
                    aria-label={`Remove ${it.recipe.title} from plan`}
                    className="grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <X className="size-4" />
                  </button>
                }
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
