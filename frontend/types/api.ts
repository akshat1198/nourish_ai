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
  session_id?: string | null; // Stage 13: persisted per-browser id for A/B bucketing
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
  variant: string | null; // Stage 13: A/B variant this response was generated under
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
  steps_enriched: boolean; // WS6: whether the method is already LLM-enriched
  source: string;
  source_url: string | null;
  attribution: string | null;
  image_url: string | null;
  license_note: string | null;
}

// WS6: POST /recipes/{id}/enrich — richer method + filled-in measures.
export interface RecipeEnrichment {
  steps: string[];
  ingredients: RecipeIngredientLine[];
  enriched: boolean; // false when the assistant was unavailable (originals kept)
}

export interface SubstituteOption {
  use: string;
  ratio: string;
  confidence?: number | null;
  enables_diets: string[];
  note?: string; // short why/how (LLM suggestions)
  source?: "curated" | "suggested"; // curated table vs LLM-suggested
}

export interface SubstitutionsResponse {
  ingredient: string;
  substitutes: SubstituteOption[];
}

export interface ModifyRequest {
  op?: "swap" | "remove";
  from_ingredient: string;
  to_ingredient?: string; // omitted for "remove"
}

export interface SwapInfo {
  from_ingredient: string;
  to_ingredient: string;
  ratio: string;
}

export interface ModifyResponse {
  recipe_id: number;
  title: string;
  operation?: "swap" | "remove";
  note?: string;
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
  approximate: boolean; // LLM-estimated (out-of-vocabulary target)
}

export interface IngredientSuggestion {
  name: string;
  category?: string | null;
  matched_alias?: string | null;
  is_group?: boolean; // a generic that matches any of its members
  members?: string[] | null; // member canonical names (groups only)
}

// POST /v1/pantry/parse — free text → recognized pantry items.
export interface PantryParseResponse {
  recognized: IngredientSuggestion[];
  unmatched: string[];
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

// Feedback loop (Stage 9). The backend log is append-only; these are the
// toggle events. Derived state comes back via GET /v1/feedback/{user_key}.
export type FeedbackAction =
  | "cooked"
  | "uncooked"
  | "liked"
  | "disliked"
  | "unrated";

export interface RecipeFeedback {
  made: boolean;
  rating: "liked" | "disliked" | null;
}

export interface FeedbackState {
  user_key: string;
  // keyed by recipe_id (string in JSON); only non-default recipes present
  recipes: Record<string, RecipeFeedback>;
}

export interface CuisineCount {
  id: string;
  label: string;
  count: number;
  children?: CuisineCount[];
}

// Saved recipes & meal plans (Stage 10). Compact card shape shared by both.
export interface RecipeSummary {
  id: number;
  title: string;
  time_minutes?: number | null;
  cuisine?: string | null;
  region?: string | null;
  image_url?: string | null;
}

export interface SavedListOut {
  recipes: RecipeSummary[];
}

export interface PlanItem {
  recipe: RecipeSummary;
  slot?: string | null;
}

export interface Plan {
  id: number;
  name: string;
  created_at: string;
  items: PlanItem[];
}

export interface PlanSummary {
  id: number;
  name: string;
  item_count: number;
  created_at: string;
}

export interface PlanListOut {
  plans: PlanSummary[];
}

export interface ShoppingItem {
  name: string;
  unit?: string | null;
  total_qty?: number | null;
  needed_for: string[];
}

export interface ShoppingListResponse {
  items: ShoppingItem[];
  unmatched_pantry: string[];
  missing_recipe_ids: number[];
}

// Online analytics (Stage 13). Fire-and-forget; the backend never blocks a
// request on this and neither does the client.
export interface EventIn {
  name: string;
  session_id?: string | null;
  recipe_id?: number | null;
  variant?: string | null;
  props?: Record<string, unknown>;
}

export interface VariantStat {
  variant: string;
  count: number;
  by_name: Record<string, number>;
}

export interface ExperimentSummary {
  experiment: string;
  total: number;
  variants: VariantStat[];
}

export interface HealthResponse {
  status: string;
  db: boolean;
  redis: boolean;
}
