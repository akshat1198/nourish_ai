"use client";

import { OptionPill } from "@/components/filters/option-pill";
import { ALLERGENS, titleCase } from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";

export function AvoidStep() {
  const { answers, setAnswers } = useFilterFlow();

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
      </p>
      <div className="flex flex-wrap gap-2">
        {ALLERGENS.map((a) => (
          <OptionPill
            key={a}
            selected={answers.exclude_allergens.includes(a)}
            onClick={() => toggle(a)}
          >
            {titleCase(a)}
          </OptionPill>
        ))}
      </div>
    </div>
  );
}
