import { apiFetch } from "@/lib/api";
import { getUserKey } from "@/lib/auth-token";
import type {
  CuisineCount,
  HealthResponse,
  IngredientSuggestion,
  PantryReplaceIn,
  PantryResponse,
  Profile,
  ProfileUpdate,
  RecipeDetail,
  RecommendRequest,
  RecommendResponse,
} from "@/types/api";

// One typed function per endpoint the UI uses.
export const api = {
  health: () => apiFetch<HealthResponse>("/health"),

  searchIngredients: (q: string) =>
    apiFetch<IngredientSuggestion[]>(`/v1/ingredients?q=${encodeURIComponent(q)}`),

  getCuisines: () => apiFetch<CuisineCount[]>("/v1/cuisines"),

  getPantry: () => apiFetch<PantryResponse>("/v1/pantry"),

  replacePantry: (body: PantryReplaceIn) =>
    apiFetch<PantryResponse>("/v1/pantry", {
      method: "PUT",
      body: JSON.stringify(body),
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
};
