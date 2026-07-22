"use client";

import { OptionPill } from "@/components/filters/option-pill";
import { MEAL_TYPES } from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";

export function MealStep() {
  const { answers, patch } = useFilterFlow();
  return (
    <div className="flex flex-wrap gap-2">
      {MEAL_TYPES.map((m) => (
        <OptionPill
          key={m.value}
          selected={answers.meal_type === m.value}
          onClick={() =>
            patch({
              meal_type: answers.meal_type === m.value ? null : m.value,
            })
          }
        >
          {m.label}
        </OptionPill>
      ))}
      <OptionPill
        selected={answers.meal_type === null}
        onClick={() => patch({ meal_type: null })}
      >
        Doesn&apos;t matter
      </OptionPill>
    </div>
  );
}
