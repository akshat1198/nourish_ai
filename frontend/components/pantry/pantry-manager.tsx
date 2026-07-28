"use client";

import { useState } from "react";
import { Lightbulb, Pin, Plus } from "lucide-react";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
import { PantryPhotoUpload } from "@/components/pantry/pantry-photo-upload";
import { IngredientLegend } from "@/components/ingredient-legend";
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
import { ApiError } from "@/lib/api";
import { usePantry, useUpdatePantry } from "@/lib/hooks/use-pantry";
import { useParsePantryImages } from "@/lib/hooks/use-parse-pantry-images";
import { dotClass, toDotCategory } from "@/lib/ingredient-category";
import { cn } from "@/lib/utils";
import type { IngredientSuggestion, PantryItem } from "@/types/api";

// Aim for a handful of ingredients so retrieval has something to match.
const MIN_INGREDIENTS = 6;

// Everyday staples that broaden matches across cuisines (all verified in the
// canonical vocabulary). Offered as one-tap adds when the pantry is sparse.
const STAPLE_SUGGESTIONS: { name: string; category: string }[] = [
  { name: "salt", category: "pantry" },
  { name: "black pepper", category: "spice" },
  { name: "olive oil", category: "pantry" },
  { name: "onion", category: "vegetable" },
  { name: "garlic", category: "vegetable" },
  { name: "eggs", category: "protein" },
  { name: "rice", category: "grain" },
  { name: "butter", category: "dairy" },
];

export function PantryManager() {
  const { data, isLoading, isError, refetch } = usePantry();
  const update = useUpdatePantry();
  const items = data?.items ?? [];
  const existing = new Set(items.map((i) => i.ingredient));

  const commit = (next: PantryItem[]) => update.mutate(next);

  // Photos → recognized items → merged into the pantry (vision parse).
  const [note, setNote] = useState<string | null>(null);
  const parseImages = useParsePantryImages();
  const addFromImages = async (files: File[]) => {
    try {
      const res = await parseImages.mutateAsync(files);
      const have = new Set(items.map((i) => i.ingredient));
      const additions = res.recognized.filter((r) => !have.has(r.name));
      if (additions.length) {
        commit([
          ...items,
          ...additions.map((r) => ({
            ingredient: r.name,
            category: r.category ?? undefined,
            is_staple: false,
          })),
        ]);
      }
      const parts: string[] = [];
      if (additions.length) parts.push(`Added ${additions.map((r) => r.name).join(", ")}`);
      if (res.unmatched.length) parts.push(`didn't recognise ${res.unmatched.join(", ")}`);
      setNote(
        parts.length
          ? parts.join(" · ")
          : res.recognized.length
            ? "Everything in those photos is already in your pantry."
            : "No food spotted — try a closer, brighter shot.",
      );
    } catch (e) {
      // Size/count/type limits come back as a 400 worth quoting verbatim.
      setNote(
        e instanceof ApiError && e.status === 400
          ? e.detail
          : "Couldn't read those photos — try again.",
      );
      throw e;
    }
  };

  const add = (s: IngredientSuggestion) => {
    if (existing.has(s.name)) return;
    commit([...items, { ingredient: s.name, category: s.category, is_staple: false }]);
  };
  const quickAddStaple = (name: string, category: string) => {
    if (existing.has(name)) return;
    commit([...items, { ingredient: name, category, is_staple: true }]);
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
      <CardHeader className="flex-col items-stretch gap-3 space-y-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div>
          <CardTitle className="font-display text-xl">Your pantry</CardTitle>
          <CardDescription>
            What&apos;s on hand plus your everyday staples. Saved for next time.
          </CardDescription>
        </div>
        <IngredientCombobox existing={existing} onAdd={add} />
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Photo intake: shoot the shelves, the model reads the ingredients off. */}
        <div className="space-y-1.5">
          <PantryPhotoUpload
            onAnalyze={addFromImages}
            isAnalyzing={parseImages.isPending}
            onUnsupported={(names) =>
              setNote(`Couldn't read ${names.join(", ")} — that file may be damaged.`)
            }
          />
          {note && <p className="text-xs text-muted-foreground">{note}</p>}
        </div>

        {!isLoading && !isError && items.length < MIN_INGREDIENTS && (
          <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
            <div className="flex items-start gap-2.5">
              <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
              <div className="space-y-2.5">
                <p className="text-sm text-foreground">
                  For the best matches, aim for{" "}
                  <span className="font-medium">6+ ingredients</span> — a couple of
                  proteins, some veg, and the everyday staples you always keep.
                </p>
                {STAPLE_SUGGESTIONS.some((s) => !existing.has(s.name)) && (
                  <div className="flex flex-wrap gap-1.5">
                    <span className="self-center text-xs text-muted-foreground">
                      Quick add:
                    </span>
                    {STAPLE_SUGGESTIONS.filter((s) => !existing.has(s.name)).map(
                      (s) => (
                        <button
                          key={s.name}
                          type="button"
                          onClick={() => quickAddStaple(s.name, s.category)}
                          className="inline-flex h-8 touch-manipulation items-center gap-1.5 rounded-full border border-border bg-card px-3 text-xs transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span
                            className={cn("size-1.5 rounded-full", dotClass(s.category))}
                            aria-hidden
                          />
                          <Plus className="size-3" />
                          {s.name}
                        </button>
                      ),
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

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

        {items.length > 0 && (
          <IngredientLegend className="border-t border-border pt-4" />
        )}
      </CardContent>
    </Card>
  );
}
