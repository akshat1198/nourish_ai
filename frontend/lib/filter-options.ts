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
  max_time_minutes: number | null; // null = any time
}

export const EMPTY_ANSWERS: FilterAnswers = {
  cuisines: [],
  meal_type: null,
  diet: null,
  nutrition_goals: [],
  exclude_allergens: [],
  disliked_ingredients: [],
  max_time_minutes: null,
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

export const TIME_OPTIONS: { value: number | null; label: string }[] = [
  { value: 15, label: "≤ 15 min" },
  { value: 30, label: "≤ 30 min" },
  { value: 45, label: "≤ 45 min" },
  { value: 60, label: "≤ 60 min" },
  { value: null, label: "Any time" },
];

// Human labels for a taxonomy id, e.g. "indian/gujarati" -> "Gujarati".
const CUISINE_LABELS: Record<string, string> = {
  asian: "Asian",
  "asian/chinese": "Chinese",
  "asian/thai": "Thai",
  "asian/japanese": "Japanese",
  "asian/filipino": "Filipino",
  "asian/korean": "Korean",
  "asian/vietnamese": "Vietnamese",
  indian: "Indian",
  "indian/north_indian": "North Indian",
  "indian/south_indian": "South Indian",
  "indian/gujarati": "Gujarati",
  "indian/punjabi": "Punjabi",
  "indian/marathi": "Marathi",
  "indian/bengali": "Bengali",
  italian: "Italian",
  mexican: "Mexican",
  mediterranean: "Mediterranean",
  "middle-eastern": "Middle Eastern",
  american: "American",
};

export function cuisineLabel(id: string): string {
  return CUISINE_LABELS[id] ?? id;
}

export function titleCase(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
