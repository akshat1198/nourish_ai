"use client";

import { OptionPill } from "@/components/filters/option-pill";
import { DIETS, NUTRITION_GOALS, dietImpliedAllergens } from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import { useConfig } from "@/lib/hooks/use-config";
import type { NutritionGoal } from "@/types/api";

export function DietStep() {
  const { answers, setAnswers } = useFilterFlow();
  // Nutrition-goal cutoffs from the backend (so "low-fat" isn't a mystery).
  const { data: config } = useConfig();
  const goalHint = (value: string) =>
    config?.nutrition_goals.find((n) => n.value === value)?.hint;

  // Changing diet can make a manually-picked allergen redundant (e.g. Vegan
  // already excludes dairy) — drop it so Review doesn't show a duplicate chip.
  // Done here (not in the Avoid step) so it applies even if the user jumps
  // straight to Review without visiting Avoid.
  const setDiet = (next: string | null) => {
    const implied = dietImpliedAllergens(next);
    setAnswers((a) => ({
      ...a,
      diet: next,
      exclude_allergens: a.exclude_allergens.filter((x) => !implied.includes(x)),
    }));
  };

  const toggleGoal = (value: NutritionGoal) =>
    setAnswers((a) => ({
      ...a,
      nutrition_goals: a.nutrition_goals.includes(value)
        ? a.nutrition_goals.filter((v) => v !== value)
        : [...a.nutrition_goals, value],
    }));

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-medium">Diet</p>
        <div className="flex flex-wrap gap-2">
          <OptionPill selected={answers.diet === null} onClick={() => setDiet(null)}>
            No preference
          </OptionPill>
          {DIETS.map((d) => (
            <OptionPill
              key={d.value}
              selected={answers.diet === d.value}
              onClick={() => setDiet(answers.diet === d.value ? null : d.value)}
            >
              {d.label}
            </OptionPill>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-medium">
          Nutrition goals{" "}
          <span className="font-normal text-muted-foreground">
            · optional, pick any
          </span>
        </p>
        <div className="flex flex-wrap gap-2">
          {NUTRITION_GOALS.map((g) => {
            const hint = goalHint(g.value);
            return (
              <OptionPill
                key={g.value}
                selected={answers.nutrition_goals.includes(g.value)}
                onClick={() => toggleGoal(g.value)}
              >
                {g.label}
                {hint && (
                  <span className="font-normal text-muted-foreground">
                    {" "}
                    · {hint}
                  </span>
                )}
              </OptionPill>
            );
          })}
        </div>
      </div>
    </div>
  );
}
