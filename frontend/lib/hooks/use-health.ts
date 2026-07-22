"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Proves the API client + CORS wiring end to end.
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: api.health,
    staleTime: 30_000,
  });
}
