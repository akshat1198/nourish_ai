"use client";

import { useEffect, useRef, useState } from "react";
import { FilterWizard } from "@/components/filters/filter-wizard";
import { ResultsList } from "@/components/results/results-list";
import { EMPTY_ANSWERS, type FilterAnswers } from "@/lib/filter-options";
import { loadLastFilters, saveLastFilters } from "@/lib/filters-storage";
import { usePantry } from "@/lib/hooks/use-pantry";
import { useProfile, useUpdateProfile } from "@/lib/hooks/use-profile";
import type { RecommendRequest } from "@/types/api";

export function FilterFlow() {
  const pantry = usePantry();
  const profile = useProfile();
  const updateProfile = useUpdateProfile();

  const [request, setRequest] = useState<RecommendRequest | null>(null);
  const [initial, setInitial] = useState<FilterAnswers | null>(null);
  const [startAtReview, setStartAtReview] = useState(false);
  const resultsRef = useRef<HTMLDivElement>(null);

  // Prefill once profile resolves — precedence: profile defaults < last-used.
  useEffect(() => {
    if (initial !== null || profile.isLoading) return;
    const p = profile.data;
    const fromProfile: FilterAnswers = {
      ...EMPTY_ANSWERS,
      diet: p?.diet ?? null,
      exclude_allergens: p?.allergens ?? [],
      disliked_ingredients: p?.disliked_ingredients ?? [],
      cuisines: p?.cuisine_prefs ?? [],
    };
    const last = loadLastFilters();
    setInitial(last ?? fromProfile);
    setStartAtReview(last !== null);
  }, [profile.isLoading, profile.data, initial]);

  const submit = (answers: FilterAnswers) => {
    saveLastFilters(answers);
    const items = pantry.data?.items ?? [];
    setRequest({
      pantry: items.map((i) => i.ingredient),
      exclude_allergens: answers.exclude_allergens,
      disliked_ingredients: answers.disliked_ingredients,
      cuisines: answers.cuisines,
      meal_type: answers.meal_type,
      nutrition_goals: answers.nutrition_goals,
      diet: answers.diet,
      max_time_minutes: answers.max_time_minutes,
      limit: 15, // surface a comfortable set (≥10 when the corpus allows)
    });
    setTimeout(
      () => resultsRef.current?.scrollIntoView({ behavior: "smooth" }),
      60,
    );
  };

  const saveDefaults = (answers: FilterAnswers) =>
    updateProfile.mutate({
      diet: answers.diet,
      allergens: answers.exclude_allergens,
      disliked_ingredients: answers.disliked_ingredients,
      cuisine_prefs: answers.cuisines,
    });

  if (initial === null) return <div className="h-40" aria-hidden />;

  return (
    <div className="space-y-8">
      <FilterWizard
        initial={initial}
        startAtReview={startAtReview}
        onSubmit={submit}
        onSaveDefaults={saveDefaults}
        savingDefaults={updateProfile.isPending}
      />
      <div ref={resultsRef} className="scroll-mt-6">
        <ResultsList request={request} />
      </div>
    </div>
  );
}
