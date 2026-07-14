// TypeScript mirrors of the FastAPI schemas. Keep in sync with
// backend/app/schemas/{recommend,pantry,ingredient,profile}.py.

export type MealType = "breakfast" | "lunch" | "dinner" | "snack" | "dessert";
export type NutritionGoal = "high_protein" | "low_calorie" | "low_fat" | "low_carb";
export type RecommendMode = "normal" | "substitution_first" | "shopping_assisted";

export interface RecommendRequest {
  pantry: string[];
  pantry_text?: string | null;
  diet?: string | null;
  exclude_allergens: string[];
  disliked_ingredients: string[];
  cuisines: string[]; // taxonomy ids: "indian" or "indian/gujarati"
  meal_type?: MealType | null;
  nutrition_goals: NutritionGoal[];
  max_time_minutes?: number | null;
  limit: number;
}

export interface SubstitutionSuggestion {
  missing: string;
  use: string;
  ratio: string;
}

export interface RankedRecipe {
  id: number;
  title: string;
  time_minutes: number;
  diet_labels: string[];
  allergens: string[];
  tags: string[];
  cuisine: string | null;
  region: string | null;
  meal_types: string[];
  nutrition: Record<string, number>;
  matched_ingredients: string[];
  missing_ingredients: string[];
  matched_essential: number;
  total_essential: number;
  score: number;
  why: string;
  substitutions: SubstitutionSuggestion[];
}

export interface RecommendResponse {
  results: RankedRecipe[];
  mode: RecommendMode;
  explanation: string | null;
  unmatched_pantry: string[];
}

export interface IngredientSuggestion {
  name: string;
  category?: string | null;
  matched_alias?: string | null;
}

export interface PantryItem {
  ingredient: string;
  category?: string | null;
  is_staple: boolean;
}

export interface PantryReplaceIn {
  items: PantryItem[];
}

export interface PantryResponse {
  items: PantryItem[];
  unmatched: string[];
}

export interface Profile {
  user_key: string;
  diet: string | null;
  allergens: string[];
  disliked_ingredients: string[];
  cuisine_prefs: string[];
}

export type ProfileUpdate = Omit<Profile, "user_key">;

export interface HealthResponse {
  status: string;
  db: boolean;
  redis: boolean;
}
