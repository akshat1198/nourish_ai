"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Nutrition-goal cutoffs from the backend (single source of truth). Stable
// constants, so cache forever — the questionnaire reads them to label each goal.
export function useConfig() {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: api.getConfig,
    staleTime: Infinity,
  });
}
