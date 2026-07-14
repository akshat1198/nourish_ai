import { apiFetch } from "@/lib/api";
import type {
  HealthResponse,
  IngredientSuggestion,
  PantryReplaceIn,
  PantryResponse,
  Profile,
  ProfileUpdate,
  RecommendRequest,
  RecommendResponse,
} from "@/types/api";

// Dev identity for path-keyed endpoints (profile). Matches the X-User-Key the
// fetch wrapper sends; Stage 5.5 replaces this with the authed identity.
const USER_KEY = process.env.NEXT_PUBLIC_DEV_USER_KEY ?? "dev-user";

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

  getProfile: () =>
    apiFetch<Profile>(`/v1/profile/${encodeURIComponent(USER_KEY)}`),

  putProfile: (body: ProfileUpdate) =>
    apiFetch<Profile>(`/v1/profile/${encodeURIComponent(USER_KEY)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  recommend: (req: RecommendRequest) =>
    apiFetch<RecommendResponse>("/v1/recommendations", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
