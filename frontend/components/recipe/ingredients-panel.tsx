"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { ServingsStepper } from "@/components/recipe/servings-stepper";
import { SwapPopover } from "@/components/recipe/swap-popover";
import { usePantry } from "@/lib/hooks/use-pantry";
import { toDotCategory } from "@/lib/ingredient-category";
import { scaleFactor, scaleLine } from "@/lib/scale";
import { cn } from "@/lib/utils";
import type { RecipeIngredientLine } from "@/types/api";

// Loose exact-name match against the pantry — highlights the confident hits
// (canonical staples like tomato/rice) without over-claiming on source-worded
// display names. A "nice to know", never load-bearing.
function usePantryNames(): Set<string> {
  const { data } = usePantry();
  return new Set((data?.items ?? []).map((i) => i.ingredient.toLowerCase()));
}

export function IngredientsPanel({
  ingredients,
  servings,
  baseServings,
  onServings,
  onSwap,
  onRemove,
  pendingSwap,
}: {
  ingredients: RecipeIngredientLine[];
  servings: number;
  baseServings: number;
  onServings: (next: number) => void;
  onSwap: (from: string, to: string) => void;
  onRemove: (from: string) => void;
  pendingSwap: boolean;
}) {
  const have = usePantryNames();
  const anyHave = ingredients.some((l) => have.has(l.name.toLowerCase()));
  const factor = scaleFactor(baseServings, servings);
  // Cooking checklist — tick off ingredients as you use them. Session-only
  // (resets when you leave the recipe or refresh). Keyed by line index so the
  // same ingredient used at two stages is checked independently.
  const [used, setUsed] = useState<Set<number>>(new Set());
  const toggleUsed = (i: number) =>
    setUsed((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-semibold tracking-tight">
          Ingredients
        </h2>
        <ServingsStepper value={servings} base={baseServings} onChange={onServings} />
      </div>
      <ul className="space-y-2">
        {ingredients.map((line, i) => {
          const onHand = have.has(line.name.toLowerCase());
          const measure = scaleLine(line, factor).text;
          const checked = used.has(i);
          return (
            <li key={`${line.name}-${i}`} className="flex items-center gap-3">
              <button
                type="button"
                role="checkbox"
                aria-checked={checked}
                aria-label={`Mark ${line.name} as used`}
                onClick={() => toggleUsed(i)}
                className={cn(
                  "relative grid size-5 shrink-0 touch-manipulation place-items-center rounded-[0.4rem] border transition-colors before:absolute before:-inset-2 before:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  checked
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border text-transparent hover:border-primary/50",
                )}
              >
                <Check className="size-3.5" />
              </button>
              <span
                className={cn(
                  "tabular w-24 shrink-0 text-right text-sm text-muted-foreground",
                  checked && "line-through opacity-50",
                )}
              >
                {measure}
              </span>
              <IngredientToken
                name={line.name}
                category={toDotCategory(line.category)}
                muted={!onHand}
                struck={checked}
              />
              <SwapPopover
                ingredient={line.name}
                onApply={(to) => onSwap(line.name, to)}
                pending={pendingSwap}
              />
              <button
                type="button"
                disabled={pendingSwap}
                onClick={() => onRemove(line.name)}
                aria-label={`Remove ${line.name} — adapt the recipe without it`}
                className="relative grid size-6 touch-manipulation place-items-center rounded-full text-muted-foreground transition-colors before:absolute before:left-1/2 before:top-1/2 before:size-11 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
              >
                <X className="size-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
      {anyHave && (
        <p className="text-xs text-muted-foreground">
          Solid tokens are already in your pantry.
        </p>
      )}
    </section>
  );
}
