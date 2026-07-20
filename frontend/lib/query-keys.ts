import type { RecommendRequest } from "@/types/api";

// Array fields are semantically sets — sort them so ["dairy","nuts"] and
// ["nuts","dairy"] resolve to the SAME query key (and the same backend Redis
// cache entry). Unsorted arrays would fork both caches (a proven bug class).
function canonicalizeRequest(req: RecommendRequest): RecommendRequest {
  return {
    ...req,
    pantry: [...req.pantry].sort(),
    exclude_allergens: [...req.exclude_allergens].sort(),
    disliked_ingredients: [...req.disliked_ingredients].sort(),
    cuisines: [...req.cuisines].sort(),
    nutrition_goals: [...req.nutrition_goals].sort(),
  };
}

export const queryKeys = {
  health: ["health"] as const,
  pantry: ["pantry"] as const,
  profile: ["profile"] as const,
  ingredients: (q: string) => ["ingredients", q] as const,
  cuisines: ["cuisines"] as const,
  recipe: (id: number) => ["recipe", id] as const,
  recommendations: (req: RecommendRequest) =>
    ["recommendations", canonicalizeRequest(req)] as const,
};
