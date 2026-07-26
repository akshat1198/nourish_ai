"use client";

import { Pencil, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DIETS,
  NUTRITION_GOALS,
  cuisineLabel,
  titleCase,
  type FilterAnswers,
} from "@/lib/filter-options";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import { useUpdateProfile } from "@/lib/hooks/use-profile";

// The editable summary. "Edit" now routes to the relevant step (real
// navigation replaces the old in-place editingReturn mode); the primary CTA
// lives in the footer via <ReviewActions />.
export function ReviewBody() {
  const { answers, setAnswers, goToStep } = useFilterFlow();

  const dietLabel = answers.diet
    ? DIETS.find((d) => d.value === answers.diet)?.label ?? answers.diet
    : null;

  const remove = <K extends keyof FilterAnswers>(key: K, value: string) =>
    setAnswers((a) => ({
      ...a,
      [key]: (a[key] as string[]).filter((v) => v !== value),
    }));
  const muted = "text-sm text-muted-foreground";

  const dietGoalsEmpty = !dietLabel && answers.nutrition_goals.length === 0;
  const dislikesEmpty = answers.disliked_ingredients.length === 0;

  return (
    <div className="space-y-4">
      <ReviewGroup
        label="Cuisine"
        empty={answers.cuisines.length === 0}
        onEdit={() => goToStep("cuisine")}
      >
        {answers.cuisines.length === 0 ? (
          <span className={muted}>Any cuisine</span>
        ) : (
          answers.cuisines.map((id) => (
            <RemovableChip
              key={id}
              label={cuisineLabel(id)}
              onRemove={() => remove("cuisines", id)}
            />
          ))
        )}
      </ReviewGroup>

      <ReviewGroup
        label="Meal"
        empty={answers.meal_type == null}
        onEdit={() => goToStep("meal")}
      >
        {answers.meal_type ? (
          <RemovableChip
            label={titleCase(answers.meal_type)}
            onRemove={() => setAnswers((a) => ({ ...a, meal_type: null }))}
          />
        ) : (
          <span className={muted}>Any meal</span>
        )}
      </ReviewGroup>

      <ReviewGroup
        label="Diet & goals"
        empty={dietGoalsEmpty}
        onEdit={() => goToStep("diet")}
      >
        {dietGoalsEmpty && <span className={muted}>No preference</span>}
        {dietLabel && (
          <RemovableChip
            label={dietLabel}
            onRemove={() => setAnswers((a) => ({ ...a, diet: null }))}
          />
        )}
        {answers.nutrition_goals.map((g) => (
          <RemovableChip
            key={g}
            label={NUTRITION_GOALS.find((n) => n.value === g)?.label ?? g}
            onRemove={() => remove("nutrition_goals", g)}
          />
        ))}
      </ReviewGroup>

      <ReviewGroup
        label="Avoid"
        empty={answers.exclude_allergens.length === 0}
        onEdit={() => goToStep("avoid")}
      >
        {answers.exclude_allergens.length === 0 ? (
          <span className={muted}>Nothing</span>
        ) : (
          answers.exclude_allergens.map((a) => (
            <RemovableChip
              key={a}
              label={titleCase(a)}
              onRemove={() => remove("exclude_allergens", a)}
            />
          ))
        )}
      </ReviewGroup>

      <ReviewGroup
        label="Dislikes"
        empty={dislikesEmpty}
        onEdit={() => goToStep("more")}
      >
        {dislikesEmpty && (
          <span className={muted}>No dislikes</span>
        )}
        {answers.disliked_ingredients.map((n) => (
          <RemovableChip
            key={n}
            label={n}
            onRemove={() => remove("disliked_ingredients", n)}
          />
        ))}
      </ReviewGroup>
    </div>
  );
}

// Footer actions for the review step: save the answer set as profile defaults,
// or run the search. Placed in the step shell's right slot.
export function ReviewActions() {
  const { answers, goToResults } = useFilterFlow();
  const updateProfile = useUpdateProfile();

  const saveDefaults = () =>
    updateProfile.mutate({
      diet: answers.diet,
      allergens: answers.exclude_allergens,
      disliked_ingredients: answers.disliked_ingredients,
      cuisine_prefs: answers.cuisines,
    });

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        onClick={saveDefaults}
        disabled={updateProfile.isPending}
      >
        {updateProfile.isPending ? "Saving…" : "Save as my defaults"}
      </Button>
      <Button className="glow-primary" onClick={goToResults}>
        <Sparkles /> Find recipes
      </Button>
    </div>
  );
}

function RemovableChip({
  label,
  onRemove,
}: {
  label: string;
  onRemove: () => void;
}) {
  return (
    <span className="inline-flex h-8 items-center gap-1 rounded-full border border-primary/25 bg-primary/10 pl-3 pr-1.5 text-sm text-foreground">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${label}`}
        className="relative grid size-5 touch-manipulation place-items-center rounded-full text-muted-foreground transition-colors before:absolute before:left-1/2 before:top-1/2 before:size-9 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="size-3" />
      </button>
    </span>
  );
}

function ReviewGroup({
  label,
  empty,
  onEdit,
  children,
}: {
  label: string;
  empty?: boolean;
  onEdit: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2 border-b border-border pb-4 last:border-0 last:pb-0">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <button
          type="button"
          onClick={onEdit}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <Pencil className="size-3.5" /> {empty ? "Add" : "Edit"}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
