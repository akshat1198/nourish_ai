"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { OptionPill } from "@/components/filters/option-pill";
import { CUISINES, type CuisineNode } from "@/lib/cuisines";
import { cuisineLabel, type FilterAnswers } from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import { useCuisines } from "@/lib/hooks/use-cuisines";
import { cn } from "@/lib/utils";

// The cuisine step keeps its region drill-down as local state — opening a
// parent (e.g. "Indian") swaps the grid for its regions, with an in-step
// "All cuisines" affordance to collapse back. The page-level Back/Next footer
// is unchanged; picks are written straight to the shared answers.
export function CuisineStep() {
  const { answers, setAnswers } = useFilterFlow();
  const [group, setGroup] = useState<string | null>(null);
  const { data: cuisineData } = useCuisines();
  const cuisineList = cuisineData ?? CUISINES;

  const set = (patch: Partial<FilterAnswers>) =>
    setAnswers((a) => ({ ...a, ...patch }));

  const toggleCuisine = (id: string) =>
    setAnswers((a) => ({
      ...a,
      cuisines: a.cuisines.includes(id)
        ? a.cuisines.filter((c) => c !== id)
        : [...a.cuisines, id],
    }));

  const cuisineSelected = (topId: string) =>
    answers.cuisines.some((c) => c === topId || c.startsWith(`${topId}/`));

  if (group) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => setGroup(null)}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> All cuisines
        </button>
        <h3 className="font-display text-lg font-semibold">
          Which {cuisineLabel(group)}?
        </h3>
        <CuisineRegions
          group={group}
          cuisineList={cuisineList}
          answers={answers}
          setAnswers={setAnswers}
        />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {cuisineList.map((c) =>
        c.children && c.children.length ? (
          <CuisineCard
            key={c.id}
            label={c.label}
            hint="pick a region →"
            count={c.count}
            selected={cuisineSelected(c.id)}
            onClick={() => setGroup(c.id)}
          />
        ) : (
          <CuisineCard
            key={c.id}
            label={c.label}
            count={c.count}
            disabled={c.count === 0}
            selected={answers.cuisines.includes(c.id)}
            onClick={() => toggleCuisine(c.id)}
          />
        ),
      )}
      <CuisineCard
        label="Any cuisine"
        selected={answers.cuisines.length === 0}
        onClick={() => set({ cuisines: [] })}
      />
    </div>
  );
}

function CuisineCard({
  label,
  hint,
  count,
  selected,
  disabled,
  onClick,
}: {
  label: string;
  hint?: string;
  count?: number;
  selected?: boolean;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={cn(
        "flex flex-col items-start gap-0.5 rounded-xl border px-4 py-3 text-left transition-[transform,background-color,border-color,color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        disabled
          ? "cursor-not-allowed border-border bg-card opacity-40"
          : "cursor-pointer hover:-translate-y-0.5",
        selected
          ? "border-primary bg-primary/10"
          : "border-border bg-card hover:bg-secondary/40",
      )}
    >
      <span className={cn("font-medium", selected && "text-primary")}>
        {label}
      </span>
      <span className="text-xs text-muted-foreground">
        {hint ?? (count != null ? `${count} recipes` : "")}
      </span>
    </button>
  );
}

function CuisineRegions({
  group,
  cuisineList,
  answers,
  setAnswers,
}: {
  group: string;
  cuisineList: CuisineNode[];
  answers: FilterAnswers;
  setAnswers: React.Dispatch<React.SetStateAction<FilterAnswers>>;
}) {
  const node = cuisineList.find((c) => c.id === group);
  const children = node?.children ?? [];
  const selectedChildren = answers.cuisines.filter((id) =>
    id.startsWith(`${group}/`),
  );
  const isAny = answers.cuisines.includes(group);

  const toggleChild = (childId: string) =>
    setAnswers((a) => {
      const others = a.cuisines.filter(
        (id) => id !== group && !id.startsWith(`${group}/`),
      );
      const cur = a.cuisines.filter((id) => id.startsWith(`${group}/`));
      const nextChildren = cur.includes(childId)
        ? cur.filter((c) => c !== childId)
        : [...cur, childId];
      return { ...a, cuisines: [...others, ...nextChildren] };
    });

  // "Doesn't matter" here means the whole cuisine (the parent id).
  const chooseAny = () =>
    setAnswers((a) => {
      const others = a.cuisines.filter(
        (id) => id !== group && !id.startsWith(`${group}/`),
      );
      return {
        ...a,
        cuisines: a.cuisines.includes(group) ? others : [...others, group],
      };
    });

  return (
    <div className="flex flex-wrap gap-2">
      {children.map((c) => (
        <OptionPill
          key={c.id}
          selected={selectedChildren.includes(c.id)}
          disabled={c.count === 0}
          onClick={() => toggleChild(c.id)}
        >
          {c.label}
          {c.count != null && (
            <span className="ml-1 text-xs opacity-55">{c.count}</span>
          )}
        </OptionPill>
      ))}
      <OptionPill selected={isAny} onClick={chooseAny}>
        Doesn&apos;t matter
      </OptionPill>
    </div>
  );
}
