"use client";

import { Pin } from "lucide-react";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
import { IngredientToken } from "@/components/ingredient-token";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePantry, useUpdatePantry } from "@/lib/hooks/use-pantry";
import { toDotCategory } from "@/lib/ingredient-category";
import type { IngredientSuggestion, PantryItem } from "@/types/api";

export function PantryManager() {
  const { data, isLoading, isError, refetch } = usePantry();
  const update = useUpdatePantry();
  const items = data?.items ?? [];
  const existing = new Set(items.map((i) => i.ingredient));

  const commit = (next: PantryItem[]) => update.mutate(next);

  const add = (s: IngredientSuggestion) => {
    if (existing.has(s.name)) return;
    commit([...items, { ingredient: s.name, category: s.category, is_staple: false }]);
  };
  const remove = (name: string) =>
    commit(items.filter((i) => i.ingredient !== name));
  const toggleStaple = (name: string) =>
    commit(
      items.map((i) =>
        i.ingredient === name ? { ...i, is_staple: !i.is_staple } : i,
      ),
    );

  const staples = items.filter((i) => i.is_staple);
  const current = items.filter((i) => !i.is_staple);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div>
          <CardTitle className="font-display text-xl">Your pantry</CardTitle>
          <CardDescription>
            What&apos;s on hand plus your everyday staples. Saved for next time.
          </CardDescription>
        </div>
        <IngredientCombobox existing={existing} onAdd={add} />
      </CardHeader>

      <CardContent className="space-y-6">
        {isLoading && (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-24 rounded-full" />
            ))}
          </div>
        )}

        {isError && (
          <div className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
            <span className="text-destructive">Couldn&apos;t load your pantry.</span>
            <Button size="sm" variant="outline" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
            Your pantry is empty — add what you have on hand to get started.
          </p>
        )}

        {staples.length > 0 && (
          <section className="space-y-2">
            <h3 className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Pin className="size-3 fill-current text-primary" />
              Staples · always on hand
            </h3>
            <div className="flex flex-wrap gap-2">
              {staples.map((i) => (
                <IngredientToken
                  key={i.ingredient}
                  name={i.ingredient}
                  category={toDotCategory(i.category)}
                  staple
                  onToggleStaple={() => toggleStaple(i.ingredient)}
                  onRemove={() => remove(i.ingredient)}
                />
              ))}
            </div>
          </section>
        )}

        {current.length > 0 && (
          <section className="space-y-2">
            {staples.length > 0 && (
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                In your kitchen now
              </h3>
            )}
            <div className="flex flex-wrap gap-2">
              {current.map((i) => (
                <IngredientToken
                  key={i.ingredient}
                  name={i.ingredient}
                  category={toDotCategory(i.category)}
                  onToggleStaple={() => toggleStaple(i.ingredient)}
                  onRemove={() => remove(i.ingredient)}
                />
              ))}
            </div>
          </section>
        )}
      </CardContent>
    </Card>
  );
}
