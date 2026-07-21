"use client";

import { useState } from "react";
import { Lightbulb, Pin, Plus, Sparkles } from "lucide-react";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
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
import { usePantry, useUpdatePantry } from "@/lib/hooks/use-pantry";
import { useParsePantry } from "@/lib/hooks/use-parse-pantry";
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

  // Free-text → recognized items → merged into the pantry (LLM parse).
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const parse = useParsePantry();
  const addFromText = () => {
    const t = text.trim();
    if (!t) return;
    parse.mutate(t, {
      onSuccess: (res) => {
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
        setNote(parts.length ? parts.join(" · ") : "Nothing new found — try naming ingredients.");
        setText("");
      },
      onError: () => setNote("Couldn't read that — try again."),
    });
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
        {/* Free-text intake: describe the pantry in a sentence, LLM extracts it. */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            addFromText();
          }}
          className="space-y-1.5"
        >
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  addFromText();
                }
              }}
              rows={2}
              placeholder="Or just describe what you have — “half a bag of spinach, a couple eggs, some paneer”"
              aria-label="Describe your pantry in plain words"
              className="min-h-0 flex-1 resize-none rounded-lg border border-border bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button
              type="submit"
              variant="outline"
              size="sm"
              disabled={parse.isPending || !text.trim()}
              className="shrink-0 gap-1.5"
            >
              <Sparkles className="size-3.5" />
              {parse.isPending ? "Reading…" : "Add"}
            </Button>
          </div>
          {note && <p className="text-xs text-muted-foreground">{note}</p>}
        </form>

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
