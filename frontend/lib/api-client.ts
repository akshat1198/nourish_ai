import { apiFetch } from "@/lib/api";
import { getUserKey } from "@/lib/auth-token";
import type {
  ConfigResponse,
  CuisineCount,
  EventIn,
  ExperimentSummary,
  FeedbackAction,
  FeedbackState,
  HealthResponse,
  IngredientSuggestion,
  PantryParseResponse,
  PantryReplaceIn,
  PantryResponse,
  ModifyRequest,
  ModifyResponse,
  Plan,
  PlanListOut,
  Profile,
  ProfileUpdate,
  RecipeDetail,
  RecipeEnrichment,
  RecommendRequest,
  RecommendResponse,
  SavedListOut,
  ShoppingListResponse,
  SubstitutionsResponse,
} from "@/types/api";

// One typed function per endpoint the UI uses.
export const api = {
  health: () => apiFetch<HealthResponse>("/health"),

  getConfig: () => apiFetch<ConfigResponse>("/v1/config"),

  searchIngredients: (q: string) =>
    apiFetch<IngredientSuggestion[]>(`/v1/ingredients?q=${encodeURIComponent(q)}`),

  getCuisines: () => apiFetch<CuisineCount[]>("/v1/cuisines"),

  getPantry: () => apiFetch<PantryResponse>("/v1/pantry"),

  replacePantry: (body: PantryReplaceIn) =>
    apiFetch<PantryResponse>("/v1/pantry", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  parsePantry: (text: string) =>
    apiFetch<PantryParseResponse>("/v1/pantry/parse", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),

  getProfile: () =>
    apiFetch<Profile>(`/v1/profile/${encodeURIComponent(getUserKey())}`),

  putProfile: (body: ProfileUpdate) =>
    apiFetch<Profile>(`/v1/profile/${encodeURIComponent(getUserKey())}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  recommend: (req: RecommendRequest) =>
    apiFetch<RecommendResponse>("/v1/recommendations", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  getRecipe: (id: number) => apiFetch<RecipeDetail>(`/v1/recipes/${id}`),

  enrichRecipe: (id: number) =>
    apiFetch<RecipeEnrichment>(`/v1/recipes/${id}/enrich`, { method: "POST" }),

  findSubstitutions: (ingredient: string) =>
    apiFetch<SubstitutionsResponse>("/v1/substitutions", {
      method: "POST",
      body: JSON.stringify({ ingredient }),
    }),

  modifyRecipe: (id: number, body: ModifyRequest) =>
    apiFetch<ModifyResponse>(`/v1/recipes/${id}/modify`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getFeedback: () =>
    apiFetch<FeedbackState>(`/v1/feedback/${encodeURIComponent(getUserKey())}`),

  sendFeedback: (recipeId: number, action: FeedbackAction) =>
    apiFetch<{ ok: boolean }>("/v1/feedback", {
      method: "POST",
      body: JSON.stringify({
        user_key: getUserKey(),
        recipe_id: recipeId,
        action,
      }),
    }),

  // Saved recipes
  getSaved: () => apiFetch<SavedListOut>("/v1/saved"),

  addSaved: (recipeId: number) =>
    apiFetch<SavedListOut>("/v1/saved", {
      method: "POST",
      body: JSON.stringify({ recipe_id: recipeId }),
    }),

  removeSaved: (recipeId: number) =>
    apiFetch<SavedListOut>(`/v1/saved/${recipeId}`, { method: "DELETE" }),

  // Meal plans
  getPlans: () => apiFetch<PlanListOut>("/v1/plans"),

  getPlan: (id: number) => apiFetch<Plan>(`/v1/plans/${id}`),

  createPlan: (name: string) =>
    apiFetch<Plan>("/v1/plans", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  deletePlan: (id: number) =>
    apiFetch<{ ok: boolean }>(`/v1/plans/${id}`, { method: "DELETE" }),

  addPlanItem: (planId: number, recipeId: number, slot?: string | null) =>
    apiFetch<Plan>(`/v1/plans/${planId}/items`, {
      method: "POST",
      body: JSON.stringify({ recipe_id: recipeId, slot: slot ?? null }),
    }),

  removePlanItem: (planId: number, recipeId: number) =>
    apiFetch<Plan>(`/v1/plans/${planId}/items/${recipeId}`, { method: "DELETE" }),

  getPlanShoppingList: (planId: number) =>
    apiFetch<ShoppingListResponse>(`/v1/plans/${planId}/shopping-list`),

  // Online analytics
  track: (body: EventIn) =>
    apiFetch<{ ok: boolean }>("/v1/events", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getExperimentSummary: (name: string) =>
    apiFetch<ExperimentSummary>(`/v1/experiments/${encodeURIComponent(name)}/summary`),
};
