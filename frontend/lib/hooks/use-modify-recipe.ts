"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { ModifyRequest } from "@/types/api";

// Applies an ingredient swap. The response (post-swap ingredients/steps/labels)
// is held in the detail view; the ~seconds sonnet call surfaces via isPending.
export function useModifyRecipe(recipeId: number) {
  return useMutation({
    mutationFn: (body: ModifyRequest) => api.modifyRecipe(recipeId, body),
  });
}
