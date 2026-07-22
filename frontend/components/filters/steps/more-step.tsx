"use client";

import { IngredientToken } from "@/components/ingredient-token";
import { OptionPill } from "@/components/filters/option-pill";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
import { TIME_OPTIONS } from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";

// Dislikes + cook time — the last filter before review.
export function MoreStep() {
  const { answers, patch } = useFilterFlow();

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium">Ingredients to avoid</p>
          <IngredientCombobox
            existing={new Set(answers.disliked_ingredients)}
            onAdd={(s) =>
              patch({
                disliked_ingredients: [...answers.disliked_ingredients, s.name],
              })
            }
          />
        </div>
        {answers.disliked_ingredients.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing you dislike — add anything you&apos;d rather skip.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {answers.disliked_ingredients.map((name) => (
              <IngredientToken
                key={name}
                name={name}
                onRemove={() =>
                  patch({
                    disliked_ingredients: answers.disliked_ingredients.filter(
                      (n) => n !== name,
                    ),
                  })
                }
              />
            ))}
          </div>
        )}
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium">Time to cook</p>
        <div className="flex flex-wrap gap-2">
          {TIME_OPTIONS.map((t) => (
            <OptionPill
              key={t.label}
              selected={answers.max_time_minutes === t.value}
              onClick={() =>
                patch({
                  max_time_minutes:
                    answers.max_time_minutes === t.value ? null : t.value,
                })
              }
            >
              {t.label}
            </OptionPill>
          ))}
        </div>
      </div>
    </div>
  );
}
