"use client";

import { useState } from "react";
import { ArrowLeft, ArrowRight, Pencil, Sparkles } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { OptionPill } from "@/components/filters/option-pill";
import { IngredientCombobox } from "@/components/pantry/ingredient-combobox";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CUISINES } from "@/lib/cuisines";
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

  const idx = STEPS.indexOf(step);
  const set = (patch: Partial<FilterAnswers>) =>
    setAnswers((a) => ({ ...a, ...patch }));
  const next = () => setStep(STEPS[Math.min(idx + 1, STEPS.length - 1)]);
  const back = () => {
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
            <span className="tabular">
              Step {idx + 1} of {STEPS.length}
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${((idx + 1) / STEPS.length) * 100}%` }}
            />
          </div>
        </div>

        <h2 className="font-display text-2xl font-semibold tracking-tight">
          {group ? `Which ${cuisineLabel(group)}?` : STEP_TITLE[step]}
        </h2>

        {/* ---- CUISINE ---- */}
        {step === "cuisine" && !group && (
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {CUISINES.map((c) =>
              c.children ? (
                <CuisineCard
                  key={c.id}
                  label={c.label}
                  hint="pick a region →"
                  selected={cuisineSelected(c.id)}
                  onClick={() => setGroup(c.id)}
                />
              ) : (
                <CuisineCard
                  key={c.id}
                  label={c.label}
                  selected={answers.cuisines.length === 1 && answers.cuisines[0] === c.id}
                  onClick={() => {
                    set({ cuisines: [c.id] });
                    next();
                  }}
                />
              ),
            )}
            <CuisineCard
              label="Any cuisine"
              selected={answers.cuisines.length === 0}
              onClick={() => {
                set({ cuisines: [] });
                next();
              }}
            />
          </div>
        )}

        {step === "cuisine" && group && (
          <CuisineSubStep
            group={group}
            answers={answers}
            setAnswers={setAnswers}
            onDone={() => {
              setGroup(null);
              next();
            }}
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
                  set({ meal_type: m.value });
                  next();
                }}
              >
                {m.label}
              </OptionPill>
            ))}
            <OptionPill
              selected={answers.meal_type === null}
              onClick={() => {
                set({ meal_type: null });
                next();
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
                    onClick={() => set({ diet: d.value })}
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
                {NUTRITION_GOALS.map((g) => (
                  <OptionPill
                    key={g.value}
                    selected={answers.nutrition_goals.includes(g.value)}
                    onClick={() => toggle("nutrition_goals", g.value)}
                  >
                    {g.label}
                  </OptionPill>
                ))}
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
                    onClick={() => set({ max_time_minutes: t.value })}
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
          <ReviewStep answers={answers} goTo={setStep} />
        )}

        {/* ---- FOOTER NAV ---- */}
        <div className="flex items-center justify-between border-t border-border pt-5">
          {idx > 0 || group ? (
            <Button variant="ghost" onClick={back}>
              <ArrowLeft /> Back
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
          ) : step === "cuisine" ? (
            <span />
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
  selected,
  onClick,
}: {
  label: string;
  hint?: string;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cn(
        "flex flex-col items-start gap-0.5 rounded-xl border px-4 py-3 text-left transition-all cursor-pointer hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        selected
          ? "border-primary bg-primary/10"
          : "border-border bg-card hover:bg-secondary/40",
      )}
    >
      <span className={cn("font-medium", selected && "text-primary")}>{label}</span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </button>
  );
}

function CuisineSubStep({
  group,
  answers,
  setAnswers,
  onDone,
}: {
  group: string;
  answers: FilterAnswers;
  setAnswers: React.Dispatch<React.SetStateAction<FilterAnswers>>;
  onDone: () => void;
}) {
  const node = CUISINES.find((c) => c.id === group);
  const children = node?.children ?? [];
  const selectedChildren = answers.cuisines.filter((id) =>
    id.startsWith(`${group}/`),
  );
  const isAny = answers.cuisines.length === 1 && answers.cuisines[0] === group;

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

  const chooseAny = () => setAnswers((a) => ({ ...a, cuisines: [group] }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {children.map((c) => (
          <OptionPill
            key={c.id}
            selected={selectedChildren.includes(c.id)}
            onClick={() => toggleChild(c.id)}
          >
            {c.label}
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
        Continue <ArrowRight />
      </Button>
    </div>
  );
}

function ReviewRow({
  label,
  value,
  onEdit,
}: {
  label: string;
  value: string;
  onEdit: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border py-3 last:border-0">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="mt-0.5 text-sm">{value}</p>
      </div>
      <button
        type="button"
        onClick={onEdit}
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <Pencil className="size-3.5" /> Edit
      </button>
    </div>
  );
}

function ReviewStep({
  answers,
  goTo,
}: {
  answers: FilterAnswers;
  goTo: (s: Step) => void;
}) {
  const cuisineText =
    answers.cuisines.length === 0
      ? "Any cuisine"
      : answers.cuisines.map(cuisineLabel).join(", ");
  const dietText = answers.diet
    ? DIETS.find((d) => d.value === answers.diet)?.label ?? answers.diet
    : "No preference";
  const goalsText =
    answers.nutrition_goals.length === 0
      ? "—"
      : answers.nutrition_goals
          .map((g) => NUTRITION_GOALS.find((n) => n.value === g)?.label ?? g)
          .join(", ");
  const timeText =
    TIME_OPTIONS.find((t) => t.value === answers.max_time_minutes)?.label ??
    "Any time";

  return (
    <div>
      <ReviewRow label="Cuisine" value={cuisineText} onEdit={() => goTo("cuisine")} />
      <ReviewRow
        label="Meal"
        value={answers.meal_type ? titleCase(answers.meal_type) : "Any meal"}
        onEdit={() => goTo("meal")}
      />
      <ReviewRow
        label="Diet & goals"
        value={`${dietText}${goalsText !== "—" ? ` · ${goalsText}` : ""}`}
        onEdit={() => goTo("dietary")}
      />
      <ReviewRow
        label="Avoid"
        value={
          answers.exclude_allergens.length
            ? answers.exclude_allergens.map(titleCase).join(", ")
            : "Nothing"
        }
        onEdit={() => goTo("allergens")}
      />
      <ReviewRow
        label="Dislikes & time"
        value={`${
          answers.disliked_ingredients.length
            ? answers.disliked_ingredients.join(", ")
            : "No dislikes"
        } · ${timeText}`}
        onEdit={() => goTo("dislikes")}
      />
    </div>
  );
}
