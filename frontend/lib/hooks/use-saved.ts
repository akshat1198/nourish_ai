"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { track } from "@/lib/track";
import type { RecipeSummary, SavedListOut } from "@/types/api";

export function useSaved() {
  return useQuery({
    queryKey: queryKeys.saved,
    queryFn: api.getSaved,
    staleTime: 60_000,
  });
}

export function useIsSaved(recipeId: number): boolean {
  const { data } = useSaved();
  return !!data?.recipes.some((r) => r.id === recipeId);
}

// Toggles save state for a recipe. Optimistically patches the saved list (using
// the passed summary so the button and Saved page update instantly), then
// reconciles with the endpoint's authoritative list on success.
export function useToggleSave(summary: RecipeSummary) {
  const qc = useQueryClient();
  const saved = useIsSaved(summary.id);

  const mutation = useMutation({
    mutationFn: () =>
      saved ? api.removeSaved(summary.id) : api.addSaved(summary.id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: queryKeys.saved });
      const prev = qc.getQueryData<SavedListOut>(queryKeys.saved);
      qc.setQueryData<SavedListOut>(queryKeys.saved, (old) => {
        const list = old?.recipes ?? [];
        if (saved) return { recipes: list.filter((r) => r.id !== summary.id) };
        if (list.some((r) => r.id === summary.id)) return { recipes: list };
        return { recipes: [summary, ...list] };
      });
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.saved, ctx.prev);
    },
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.saved, data);
      if (!saved) track("saved", { recipe_id: summary.id });
    },
  });

  return { saved, toggle: mutation.mutate, pending: mutation.isPending };
}
