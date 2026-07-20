"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Recipes are immutable once ingested, so cache aggressively — an hour keeps
// back-and-forth between results and detail instant without a refetch.
export function useRecipe(id: number) {
  return useQuery({
    queryKey: queryKeys.recipe(id),
    queryFn: () => api.getRecipe(id),
    enabled: Number.isFinite(id),
    staleTime: 3600_000,
  });
}
