"use client";

import { IngredientToken } from "@/components/ingredient-token";
import { usePantry } from "@/lib/hooks/use-pantry";
import { toDotCategory } from "@/lib/ingredient-category";
import type { RecipeIngredientLine } from "@/types/api";

// Loose exact-name match against the pantry — highlights the confident hits
// (canonical staples like tomato/rice) without over-claiming on source-worded
// display names. A "nice to know", never load-bearing.
function usePantryNames(): Set<string> {
  const { data } = usePantry();
  return new Set((data?.items ?? []).map((i) => i.ingredient.toLowerCase()));
}

function measureOf(line: RecipeIngredientLine): string {
  if (line.qty != null) return `${line.qty} ${line.unit ?? ""}`.trim();
  return line.unit ?? "";
}

export function IngredientsPanel({
  ingredients,
}: {
  ingredients: RecipeIngredientLine[];
}) {
  const have = usePantryNames();
  const anyHave = ingredients.some((l) => have.has(l.name.toLowerCase()));

  return (
    <section className="space-y-3">
      <h2 className="font-display text-2xl font-semibold tracking-tight">
        Ingredients
      </h2>
      <ul className="space-y-2">
        {ingredients.map((line, i) => {
          const onHand = have.has(line.name.toLowerCase());
          const measure = measureOf(line);
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
