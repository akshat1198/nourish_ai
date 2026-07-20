"use client";

import { X } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { ServingsStepper } from "@/components/recipe/servings-stepper";
import { SwapPopover } from "@/components/recipe/swap-popover";
import { usePantry } from "@/lib/hooks/use-pantry";
import { toDotCategory } from "@/lib/ingredient-category";
import { scaleFactor, scaleLine } from "@/lib/scale";
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
          return (
            <li key={`${line.name}-${i}`} className="flex items-center gap-3">
              <span className="tabular w-24 shrink-0 text-right text-sm text-muted-foreground">
                {measure}
              </span>
              <IngredientToken
                name={line.name}
                category={toDotCategory(line.category)}
                muted={!onHand}
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
