import { CUISINES, type CuisineNode } from "@/lib/cuisines";

import type { MealType, NutritionGoal } from "@/types/api";

// The questionnaire's working state (frontend-only; composed into a
// RecommendRequest at submit, with pantry pulled from the cache).
export interface FilterAnswers {
  cuisines: string[]; // taxonomy ids ("indian" or "indian/gujarati"); [] = any
  meal_type: MealType | null;
  diet: string | null; // vegetarian | vegan | gluten_free | null
  nutrition_goals: NutritionGoal[];
  exclude_allergens: string[];
  disliked_ingredients: string[];
}

export const EMPTY_ANSWERS: FilterAnswers = {
  cuisines: [],
  meal_type: null,
  diet: null,
  nutrition_goals: [],
  exclude_allergens: [],
  disliked_ingredients: [],
};

export const MEAL_TYPES: { value: MealType; label: string }[] = [
  { value: "breakfast", label: "Breakfast" },
  { value: "lunch", label: "Lunch" },
  { value: "dinner", label: "Dinner" },
  { value: "snack", label: "Snack" },
  { value: "dessert", label: "Dessert" },
];

export const DIETS: { value: string; label: string }[] = [
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "gluten_free", label: "Gluten-free" },
];

export const NUTRITION_GOALS: { value: NutritionGoal; label: string }[] = [
  { value: "high_protein", label: "High-protein" },
  { value: "low_calorie", label: "Low-calorie" },
  { value: "low_fat", label: "Low-fat" },
  { value: "low_carb", label: "Low-carb" },
];

export const ALLERGENS: string[] = [
  "dairy",
  "gluten",
  "nuts",
  "peanuts",
  "eggs",
  "soy",
  "shellfish",
  "fish",
  "sesame",
];

// Human labels for a taxonomy id, e.g. "indian/gujarati" -> "Gujarati".
// Derived from the CUISINES tree rather than hand-listed: the two were
// maintained separately and drifted, so ids present in the tree but missing
// here rendered as raw slugs ("african/kenyan") in chips and cards.
const CUISINE_LABELS: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  const walk = (nodes: CuisineNode[]) => {
    for (const node of nodes) {
      out[node.id] = node.label;
      if (node.children) walk(node.children);
    }
  };
  walk(CUISINES);
  return out;
})();

// Allergens a diet choice already guarantees excluded, per the backend's own
// derivation truth (app/services/derivation.py::classify_and_derive): "vegan"
// requires every matched ingredient to be vegan-flagged, which the non-vegan
// keyword backstop ties to dairy/eggs/fish/shellfish; "vegetarian" (non-vegan)
// only zeroes out on meat/fish/shellfish keywords, so dairy/eggs still apply;
// "gluten_free" trivially implies no gluten. Used to grey out and explain
// redundant allergen picks in the Avoid step, not to change what's sent to
// the backend (diet and exclude_allergens stay independent AND filters there).
export function dietImpliedAllergens(diet: string | null): string[] {
  switch (diet) {
    case "vegan":
      return ["dairy", "eggs", "fish", "shellfish"];
    case "vegetarian":
      return ["fish", "shellfish"];
    case "gluten_free":
      return ["gluten"];
    default:
      return [];
  }
}

export function cuisineLabel(id: string): string {
  return CUISINE_LABELS[id] ?? id;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
