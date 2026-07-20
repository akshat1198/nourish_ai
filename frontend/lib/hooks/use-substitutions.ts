"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Fetched lazily when a swap popover opens (enabled), then cached for the
// session — the substitution table is static between ingests.
export function useSubstitutions(ingredient: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.substitutions(ingredient),
    queryFn: () => api.findSubstitutions(ingredient),
    enabled: enabled && ingredient.length > 0,
    staleTime: Infinity,
  });
}
