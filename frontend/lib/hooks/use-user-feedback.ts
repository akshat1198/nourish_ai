"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { RecipeFeedback } from "@/types/api";

const DEFAULT: RecipeFeedback = { made: false, rating: null };

// Derived feedback state for the current user, keyed by recipe id.
export function useUserFeedback() {
  return useQuery({
    queryKey: queryKeys.feedback,
    queryFn: api.getFeedback,
    staleTime: 60_000,
  });
}

// Convenience: this recipe's current state (default when untouched).
export function useRecipeFeedback(recipeId: number): RecipeFeedback {
  const { data } = useUserFeedback();
  return data?.recipes[String(recipeId)] ?? DEFAULT;
}
