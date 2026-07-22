import { apiFetch } from "@/lib/api";
import { getUserKey } from "@/lib/auth-token";
import type {
  ConfigResponse,
  CuisineCount,
  FeedbackAction,
  FeedbackState,
  HealthResponse,
  IngredientSuggestion,
  PantryParseResponse,
  PantryReplaceIn,
  PantryResponse,
  ModifyRequest,
  ModifyResponse,
  Profile,
  ProfileUpdate,
  RecipeDetail,
  RecipeEnrichment,
  RecommendRequest,
  RecommendResponse,
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
};
