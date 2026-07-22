"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Check, Plus } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { api } from "@/lib/api-client";
import { usePlans } from "@/lib/hooks/use-plans";
import { queryKeys } from "@/lib/query-keys";
import type { Plan } from "@/types/api";

// "Add to plan" popover: pick one of the user's plans (or create a new one) to
// drop this recipe into. Adds to the null slot; the plan page lets you label it.
export function AddToPlan({ recipeId }: { recipeId: number }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [addedTo, setAddedTo] = useState<number | null>(null);
  const { data } = usePlans();
  const qc = useQueryClient();
  const plans = data?.plans ?? [];

  const cachePlan = (plan: Plan) => {
    qc.setQueryData(queryKeys.plan(plan.id), plan);
    qc.invalidateQueries({ queryKey: queryKeys.plans });
    qc.invalidateQueries({ queryKey: queryKeys.planShopping(plan.id) });
    setAddedTo(plan.id);
  };

  const add = useMutation({
    mutationFn: (planId: number) => api.addPlanItem(planId, recipeId, null),
    onSuccess: cachePlan,
  });

  const createAndAdd = useMutation({
    mutationFn: async (planName: string) => {
      const plan = await api.createPlan(planName);
      return api.addPlanItem(plan.id, recipeId, null);
    },
    onSuccess: (plan) => {
      cachePlan(plan);
      setName("");
    },
  });

  const busy = add.isPending || createAndAdd.isPending;

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setAddedTo(null);
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Add to a meal plan"
          className="inline-flex h-9 touch-manipulation items-center justify-center gap-1.5 rounded-full border border-border bg-card px-3.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <CalendarPlus className="size-4" /> Add to plan
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-64 space-y-3" align="start">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Add to a plan
        </p>

        {plans.length > 0 && (
          <div className="space-y-1">
            {plans.map((p) => (
              <button
                key={p.id}
                type="button"
                disabled={busy}
                onClick={() => add.mutate(p.id)}
                className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="truncate">{p.name}</span>
                {addedTo === p.id ? (
                  <Check className="size-4 shrink-0 text-primary" />
                ) : (
                  <Plus className="size-4 shrink-0 text-muted-foreground" />
                )}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            const n = name.trim();
            if (n) createAndAdd.mutate(n);
          }}
          className="flex items-center gap-1.5 border-t border-border pt-3"
        >
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New plan…"
            aria-label="New plan name"
            maxLength={120}
            className="h-9 flex-1 rounded-lg border border-border bg-transparent px-2.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="submit"
            disabled={busy || !name.trim()}
            aria-label="Create plan and add"
            className="grid size-9 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="size-4" />
          </button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
