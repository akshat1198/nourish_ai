"use client";

import { OptionPill } from "@/components/filters/option-pill";
import {
  ALLERGENS,
  DIETS,
  dietImpliedAllergens,
  titleCase,
} from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";

export function AvoidStep() {
  const { answers, setAnswers } = useFilterFlow();
  // Already guaranteed by the diet choice (e.g. Vegan → no dairy/eggs/fish/
  // shellfish) — shown checked-and-disabled for context, not re-selectable.
  const implied = dietImpliedAllergens(answers.diet);
  const dietLabel = DIETS.find((d) => d.value === answers.diet)?.label ?? "";

  const toggle = (value: string) =>
    setAnswers((a) => ({
      ...a,
      exclude_allergens: a.exclude_allergens.includes(value)
        ? a.exclude_allergens.filter((v) => v !== value)
        : [...a.exclude_allergens, value],
    }));

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        We&apos;ll never recommend a recipe with these.
        {implied.length > 0 && (
          <>
            {" "}
            Your {dietLabel.toLowerCase()} choice already covers a few of
            these — shown below for reference.
          </>
        )}
      </p>
      <div className="flex flex-wrap gap-2">
        {ALLERGENS.map((a) => {
          const isImplied = implied.includes(a);
          return (
            <OptionPill
              key={a}
              selected={isImplied || answers.exclude_allergens.includes(a)}
              disabled={isImplied}
              onClick={() => toggle(a)}
            >
              {titleCase(a)}
              {isImplied && (
                <span className="font-normal">
                  {" "}
                  · already {dietLabel.toLowerCase()}
                </span>
              )}
            </OptionPill>
          );
        })}
      </div>
    </div>
  );
}
