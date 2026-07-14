import { apiFetch } from "@/lib/api";
import type {
  HealthResponse,
  IngredientSuggestion,
  PantryReplaceIn,
  PantryResponse,
  RecommendRequest,
  RecommendResponse,
} from "@/types/api";

// One typed function per endpoint the UI uses.
export const api = {
  health: () => apiFetch<HealthResponse>("/health"),

  searchIngredients: (q: string) =>
    apiFetch<IngredientSuggestion[]>(`/v1/ingredients?q=${encodeURIComponent(q)}`),

  getPantry: () => apiFetch<PantryResponse>("/v1/pantry"),

  replacePantry: (body: PantryReplaceIn) =>
    apiFetch<PantryResponse>("/v1/pantry", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  recommend: (req: RecommendRequest) =>
    apiFetch<RecommendResponse>("/v1/recommendations", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
