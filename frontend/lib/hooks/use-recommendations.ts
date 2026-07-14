"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { RecommendRequest } from "@/types/api";

// POST-as-query: the submitted filter payload is the key. staleTime matches the
// backend's 300s Redis TTL (re-hitting inside that window is pure waste), and
// keepPreviousData keeps the last results on screen while a new combo loads.
export function useRecommendations(request: RecommendRequest | null) {
  return useQuery({
    queryKey: request
      ? queryKeys.recommendations(request)
      : ["recommendations", "idle"],
    queryFn: () => api.recommend(request!),
    enabled: request !== null,
    staleTime: 300_000,
    placeholderData: keepPreviousData,
  });
}
