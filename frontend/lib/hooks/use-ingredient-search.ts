"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Autocomplete against the canonical vocabulary. Debounce the input upstream;
// the vocab is static per session so results never go stale.
export function useIngredientSearch(q: string) {
  return useQuery({
    queryKey: queryKeys.ingredients(q),
    queryFn: () => api.searchIngredients(q),
    enabled: q.trim().length >= 1,
    staleTime: Infinity,
  });
}
