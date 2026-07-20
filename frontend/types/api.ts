// TypeScript mirrors of the FastAPI schemas. Keep in sync with
// backend/app/schemas/{recommend,pantry,ingredient,profile}.py.

export type MealType = "breakfast" | "lunch" | "dinner" | "snack" | "dessert";
export type NutritionGoal = "high_protein" | "low_calorie" | "low_fat" | "low_carb";
export type RecommendMode =
  | "normal"
  | "substitution_first"
  | "shopping_assisted"
  | "relaxed";

// GET /v1/config — the nutrition-goal cutoffs, so the UI can show what each goal
// means without hardcoding numbers that could drift from the backend.
export interface NutritionThreshold {
  value: NutritionGoal;
  hint: string;
}
export interface ConfigResponse {
  nutrition_goals: NutritionThreshold[];
}

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

export interface RecipeIngredientLine {
  name: string;
  qty: number | null;
  unit: string | null;
  essential: boolean;
  category: string | null;
}

export interface RecipeDetail {
  id: number;
  title: string;
  description: string;
  cuisine: string | null;
  region: string | null;
  meal_types: string[];
  tags: string[];
  diet_labels: string[];
  allergens: string[];
  time_minutes: number;
  servings: number;
  nutrition: Record<string, number>;
  nutrition_estimated: boolean;
  ingredients: RecipeIngredientLine[];
  steps: string[];
  source: string;
  source_url: string | null;
  attribution: string | null;
  image_url: string | null;
  license_note: string | null;
}

export interface SubstituteOption {
  use: string;
  ratio: string;
  confidence: number;
  enables_diets: string[];
}

export interface SubstitutionsResponse {
  ingredient: string;
  substitutes: SubstituteOption[];
}

export interface ModifyRequest {
  from_ingredient: string;
  to_ingredient: string;
}

export interface SwapInfo {
  from_ingredient: string;
  to_ingredient: string;
  ratio: string;
}

export interface ModifyResponse {
  recipe_id: number;
  title: string;
  swap: SwapInfo;
  ingredients: RecipeIngredientLine[];
  steps: string[];
  changed_step_indexes: number[];
  diet_labels: string[];
  allergens: string[];
  added_allergens: string[];
  removed_allergens: string[];
  nutrition: Record<string, number>;
  nutrition_delta: Record<string, number>;
  knock_on_flags: string[];
  warnings: string[];
  llm_used: boolean;
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

export interface CuisineCount {
  id: string;
  label: string;
  count: number;
  children?: CuisineCount[];
}

export interface HealthResponse {
  status: string;
  db: boolean;
  redis: boolean;
}
