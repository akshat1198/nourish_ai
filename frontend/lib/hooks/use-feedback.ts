"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { track } from "@/lib/track";
import type { FeedbackAction, FeedbackState, RecipeFeedback } from "@/types/api";

const DEFAULT: RecipeFeedback = { made: false, rating: null };

// Translate a toggle event into the resulting derived state (mirrors the
// backend's latest-wins fold) so the optimistic patch matches the eventual
// server response.
function applyLocal(cur: RecipeFeedback, action: FeedbackAction): RecipeFeedback {
  switch (action) {
    case "cooked":
      return { ...cur, made: true };
    case "uncooked":
      return { ...cur, made: false };
    case "liked":
      return { ...cur, rating: "liked" };
    case "disliked":
      return { ...cur, rating: "disliked" };
    case "unrated":
      return { ...cur, rating: null };
  }
}

// Posts a feedback event and optimistically patches the feedback cache; the
// filled button state IS the confirmation. Rolls back on error.
export function useFeedback(recipeId: number) {
  const qc = useQueryClient();
  const key = String(recipeId);

  return useMutation({
    mutationFn: (action: FeedbackAction) => api.sendFeedback(recipeId, action),
    onMutate: async (action) => {
      await qc.cancelQueries({ queryKey: queryKeys.feedback });
      const prev = qc.getQueryData<FeedbackState>(queryKeys.feedback);
      qc.setQueryData<FeedbackState>(queryKeys.feedback, (old) => {
        const base: FeedbackState = old ?? { user_key: "", recipes: {} };
        const next = applyLocal(base.recipes[key] ?? DEFAULT, action);
        const recipes = { ...base.recipes };
        // drop all-default entries so state mirrors the server (which omits them)
        if (!next.made && next.rating === null) delete recipes[key];
        else recipes[key] = next;
        return { ...base, recipes };
      });
      return { prev };
    },
    onError: (_e, _action, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.feedback, ctx.prev);
    },
    onSuccess: (_data, action) => {
      if (action === "cooked") track("cooked", { recipe_id: recipeId });
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.feedback }),
  });
}
