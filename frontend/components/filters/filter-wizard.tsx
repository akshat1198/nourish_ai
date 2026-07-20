"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Pencil, Sparkles, X } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { OptionPill } from "@/components/filters/option-pill";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CUISINES, type CuisineNode } from "@/lib/cuisines";
import { useConfig } from "@/lib/hooks/use-config";
import { useCuisines } from "@/lib/hooks/use-cuisines";
import {
  ALLERGENS,
  DIETS,
  MEAL_TYPES,
  NUTRITION_GOALS,
  TIME_OPTIONS,
  cuisineLabel,
  titleCase,
  type FilterAnswers,
} from "@/lib/filter-options";
import { cn } from "@/lib/utils";

const STEPS = ["cuisine", "meal", "dietary", "allergens", "dislikes", "review"] as const;
type Step = (typeof STEPS)[number];

const STEP_TITLE: Record<Step, string> = {
  cuisine: "What are you in the mood for?",
  meal: "Which meal?",
  dietary: "How do you want to eat?",
  allergens: "Anything to avoid?",
  dislikes: "Dislikes & time",
  review: "Ready to cook?",
};

interface Props {
  initial: FilterAnswers;
  startAtReview: boolean;
  onSubmit: (a: FilterAnswers) => void;
  onSaveDefaults: (a: FilterAnswers) => void;
  savingDefaults: boolean;
}

export function FilterWizard({
  initial,
  startAtReview,
  onSubmit,
  onSaveDefaults,
  savingDefaults,
}: Props) {
  const [answers, setAnswers] = useState<FilterAnswers>(initial);
  const [step, setStep] = useState<Step>(startAtReview ? "review" : "cuisine");
  const [group, setGroup] = useState<string | null>(null); // cuisine drill-down
  // True when a single filter was opened from the review — selecting returns
  // straight to review instead of walking the rest of the wizard.
  const [editingReturn, setEditingReturn] = useState(false);
  // Live taxonomy + counts (6.4); falls back to the static list while loading.
  const { data: cuisineData } = useCuisines();
  const cuisineList = cuisineData ?? CUISINES;
  // Nutrition-goal cutoffs from the backend (shown on each goal so "low-fat"
  // isn't a mystery); undefined until loaded.
  const { data: config } = useConfig();
  const goalHint = (value: string) =>
    config?.nutrition_goals.find((n) => n.value === value)?.hint;

  const idx = STEPS.indexOf(step);
  const set = (patch: Partial<FilterAnswers>) =>
    setAnswers((a) => ({ ...a, ...patch }));
  const next = () => setStep(STEPS[Math.min(idx + 1, STEPS.length - 1)]);
  const toReview = () => {
    setEditingReturn(false);
    setGroup(null);
    setStep("review");
  };
  const advance = () => {
    setGroup(null);
    if (editingReturn) toReview();
    else next();
  };
  const startEdit = (target: Step) => {
    setGroup(null);
    setEditingReturn(true);
    setStep(target);
  };
  const back = () => {
    if (editingReturn) return toReview();
    if (group) return setGroup(null);
    setStep(STEPS[Math.max(idx - 1, 0)]);
  };

  const toggle = <K extends "nutrition_goals" | "exclude_allergens">(
    key: K,
    value: string,
  ) =>
    setAnswers((a) => {
      const arr = a[key] as string[];
      return {
        ...a,
        [key]: arr.includes(value)
          ? arr.filter((v) => v !== value)
          : [...arr, value],
      };
    });

  // Cuisines are additive (pick several) and toggle off when re-clicked.
  const toggleCuisine = (id: string) =>
    setAnswers((a) => ({
      ...a,
      cuisines: a.cuisines.includes(id)
        ? a.cuisines.filter((c) => c !== id)
        : [...a.cuisines, id],
    }));

  // ---- cuisine helpers ---------------------------------------------------- #
  const cuisineSelected = (topId: string) =>
    answers.cuisines.some((c) => c === topId || c.startsWith(`${topId}/`));

  return (
    <Card>
      <CardContent className="space-y-6 pt-5">
        {/* progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wide">
              Tonight&apos;s recipe
            </span>
            {!editingReturn && (
              <span className="tabular">
                Step {idx + 1} of {STEPS.length}
              </span>
            )}
          </div>
          {!editingReturn && (
            <div className="h-1 overflow-hidden rounded-full bg-secondary">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-300"
                style={{ width: `${((idx + 1) / STEPS.length) * 100}%` }}
              />
            </div>
          )}
        </div>

        <h2 className="font-display text-2xl font-semibold tracking-tight">
          {group ? `Which ${cuisineLabel(group)}?` : STEP_TITLE[step]}
        </h2>

        {/* ---- CUISINE ---- */}
        {step === "cuisine" && !group && (
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
        )}

        {step === "cuisine" && group && (
          <CuisineSubStep
            group={group}
            cuisineList={cuisineList}
            answers={answers}
            setAnswers={setAnswers}
            editing={editingReturn}
            onDone={advance}
          />
        )}

        {/* ---- MEAL ---- */}
        {step === "meal" && (
          <div className="flex flex-wrap gap-2">
            {MEAL_TYPES.map((m) => (
              <OptionPill
                key={m.value}
                selected={answers.meal_type === m.value}
                onClick={() => {
                  set({
                    meal_type: answers.meal_type === m.value ? null : m.value,
                  });
                  advance();
                }}
              >
                {m.label}
              </OptionPill>
            ))}
            <OptionPill
              selected={answers.meal_type === null}
              onClick={() => {
                set({ meal_type: null });
                advance();
              }}
            >
              Doesn&apos;t matter
            </OptionPill>
          </div>
        )}

        {/* ---- DIETARY ---- */}
        {step === "dietary" && (
          <div className="space-y-6">
            <div className="space-y-2">
              <p className="text-sm font-medium">Diet</p>
              <div className="flex flex-wrap gap-2">
                <OptionPill
                  selected={answers.diet === null}
                  onClick={() => set({ diet: null })}
                >
                  No preference
                </OptionPill>
                {DIETS.map((d) => (
                  <OptionPill
                    key={d.value}
                    selected={answers.diet === d.value}
                    onClick={() =>
                      set({ diet: answers.diet === d.value ? null : d.value })
                    }
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
                      onClick={() => toggle("nutrition_goals", g.value)}
                    >
                      {g.label}
                      {hint && (
                        <span className="font-normal text-muted-foreground">
                          · {hint}
                        </span>
                      )}
                    </OptionPill>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ---- ALLERGENS ---- */}
        {step === "allergens" && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              We&apos;ll never recommend a recipe with these.
            </p>
            <div className="flex flex-wrap gap-2">
              {ALLERGENS.map((a) => (
                <OptionPill
                  key={a}
                  selected={answers.exclude_allergens.includes(a)}
                  onClick={() => toggle("exclude_allergens", a)}
                >
                  {titleCase(a)}
                </OptionPill>
              ))}
            </div>
          </div>
        )}

        {/* ---- DISLIKES + TIME ---- */}
        {step === "dislikes" && (
          <div className="space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">Ingredients to avoid</p>
                <IngredientCombobox
                  existing={new Set(answers.disliked_ingredients)}
                  onAdd={(s) =>
                    set({
                      disliked_ingredients: [
                        ...answers.disliked_ingredients,
                        s.name,
                      ],
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
                        set({
                          disliked_ingredients:
                            answers.disliked_ingredients.filter((n) => n !== name),
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
                      set({
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
        )}

        {/* ---- REVIEW ---- */}
        {step === "review" && (
          <ReviewStep
            answers={answers}
            setAnswers={setAnswers}
            onEdit={startEdit}
          />
        )}

        {/* ---- FOOTER NAV ---- */}
        <div className="flex items-center justify-between border-t border-border pt-5">
          {idx > 0 || group || editingReturn ? (
            <Button variant="ghost" onClick={back}>
              <ArrowLeft /> {editingReturn ? "Back to summary" : "Back"}
            </Button>
          ) : (
            <span />
          )}

          {step === "review" ? (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => onSaveDefaults(answers)}
                disabled={savingDefaults}
              >
                {savingDefaults ? "Saving…" : "Save as my defaults"}
              </Button>
              <Button className="glow-primary" onClick={() => onSubmit(answers)}>
                <Sparkles /> Find recipes
              </Button>
            </div>
          ) : group ? (
            <span />
          ) : editingReturn ? (
            <Button onClick={toReview}>Done</Button>
          ) : (
            <Button onClick={next}>
              Continue <ArrowRight />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
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
      <span className={cn("font-medium", selected && "text-primary")}>{label}</span>
      <span className="text-xs text-muted-foreground">
        {hint ?? (count != null ? `${count} recipes` : "")}
      </span>
    </button>
  );
}

function CuisineSubStep({
  group,
  cuisineList,
  answers,
  setAnswers,
  editing,
  onDone,
}: {
  group: string;
  cuisineList: CuisineNode[];
  answers: FilterAnswers;
  setAnswers: React.Dispatch<React.SetStateAction<FilterAnswers>>;
  editing: boolean;
  onDone: () => void;
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
    <div className="space-y-4">
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
      <Button
        onClick={() => {
          if (selectedChildren.length === 0 && !isAny) chooseAny();
          onDone();
        }}
      >
        {editing ? "Done" : "Continue"} <ArrowRight />
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

function ReviewStep({
  answers,
  setAnswers,
  onEdit,
}: {
  answers: FilterAnswers;
  setAnswers: React.Dispatch<React.SetStateAction<FilterAnswers>>;
  onEdit: (s: Step) => void;
}) {
  const dietLabel = answers.diet
    ? DIETS.find((d) => d.value === answers.diet)?.label ?? answers.diet
    : null;
  const timeLabel =
    answers.max_time_minutes != null
      ? TIME_OPTIONS.find((t) => t.value === answers.max_time_minutes)?.label ??
        `${answers.max_time_minutes} min`
      : null;

  const remove = <K extends keyof FilterAnswers>(key: K, value: string) =>
    setAnswers((a) => ({
      ...a,
      [key]: (a[key] as string[]).filter((v) => v !== value),
    }));
  const muted = "text-sm text-muted-foreground";

  const dietGoalsEmpty = !dietLabel && answers.nutrition_goals.length === 0;
  const dislikesTimeEmpty =
    answers.disliked_ingredients.length === 0 && timeLabel == null;

  return (
    <div className="space-y-4">
      <ReviewGroup
        label="Cuisine"
        empty={answers.cuisines.length === 0}
        onEdit={() => onEdit("cuisine")}
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
        onEdit={() => onEdit("meal")}
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
        onEdit={() => onEdit("dietary")}
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
        onEdit={() => onEdit("allergens")}
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
        label="Dislikes & time"
        empty={dislikesTimeEmpty}
        onEdit={() => onEdit("dislikes")}
      >
        {dislikesTimeEmpty && (
          <span className={muted}>No dislikes · Any time</span>
        )}
        {answers.disliked_ingredients.map((n) => (
          <RemovableChip
            key={n}
            label={n}
            onRemove={() => remove("disliked_ingredients", n)}
          />
        ))}
        {timeLabel && (
          <RemovableChip
            label={timeLabel}
            onRemove={() =>
              setAnswers((a) => ({ ...a, max_time_minutes: null }))
            }
          />
        )}
      </ReviewGroup>
    </div>
  );
}
