"use client";

import { useState } from "react";
import Link from "next/link";
import { CalendarDays, ChevronRight, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCreatePlan,
  useDeletePlan,
  usePlans,
} from "@/lib/hooks/use-plans";

export default function PlansPage() {
  const { data, isLoading } = usePlans();
  const create = useCreatePlan();
  const del = useDeletePlan();
  const [name, setName] = useState("");
  const plans = data?.plans ?? [];

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n) return;
    create.mutate(n, { onSuccess: () => setName("") });
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl font-semibold tracking-tight">
          Meal plans
        </h1>
        <p className="mt-2 text-muted-foreground">
          Group recipes for the week and get one combined shopping list.
        </p>
      </div>

      <form onSubmit={submit} className="flex items-center gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name a plan — e.g. “This week”"
          aria-label="New plan name"
          maxLength={120}
          className="h-10 flex-1 rounded-lg border border-border bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button type="submit" disabled={create.isPending || !name.trim()} className="gap-1.5">
          <Plus className="size-4" /> New plan
        </Button>
      </form>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      )}

      {!isLoading && plans.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-12 text-center">
          <CalendarDays className="mx-auto size-6 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            No plans yet. Create one above, then add recipes from any recipe page.
          </p>
        </div>
      )}

      {plans.length > 0 && (
        <div className="space-y-2">
          {plans.map((p) => (
            <Card key={p.id} className="flex items-center gap-3 p-4">
              <Link href={`/app/plans/${p.id}`} className="min-w-0 flex-1">
                <p className="font-display text-lg font-semibold leading-tight">
                  {p.name}
                </p>
                <p className="text-sm text-muted-foreground">
                  {p.item_count} {p.item_count === 1 ? "recipe" : "recipes"}
                </p>
              </Link>
              <button
                type="button"
                onClick={() => del.mutate(p.id)}
                aria-label={`Delete ${p.name}`}
                className="grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Trash2 className="size-4" />
              </button>
              <Link
                href={`/app/plans/${p.id}`}
                aria-label={`Open ${p.name}`}
                className="grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
              >
                <ChevronRight className="size-5" />
              </Link>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
