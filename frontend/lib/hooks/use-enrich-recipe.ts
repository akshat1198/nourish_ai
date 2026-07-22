"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Kicks off the one-time enrichment when a recipe is opened un-enriched.
// The endpoint is idempotent + cached server-side, so this runs at most once per
// recipe globally; the result is cached here for the session too.
export function useEnrichRecipe(id: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.enrichment(id),
    queryFn: () => api.enrichRecipe(id),
    enabled,
    staleTime: Infinity,
    retry: 1,
  });
}
