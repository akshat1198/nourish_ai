"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

// Edamam "search the wider web" (6.5). Supplemental discovery/link-out — these
// results never enter the pantry-matched corpus. Off (enabled=false) until
// Edamam creds are configured on the backend.
export function useWebSearch(q: string) {
  return useQuery({
    queryKey: queryKeys.webSearch(q),
    queryFn: () => api.searchWeb(q),
    enabled: q.trim().length >= 2,
    staleTime: 5 * 60 * 1000,
  });
}
