"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// The authored taxonomy annotated with live per-node recipe counts (6.4). The
// questionnaire uses this to grey out zero-count nodes and drill into regions
// that actually have recipes. Counts shift only on corpus ingest, so cache it
// for the session.
export function useCuisines() {
  return useQuery({
    queryKey: queryKeys.cuisines,
    queryFn: api.getCuisines,
    staleTime: Infinity,
  });
}
