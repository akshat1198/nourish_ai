"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { PantryItem, PantryResponse } from "@/types/api";

export function usePantry() {
  return useQuery({
    queryKey: queryKeys.pantry,
    queryFn: api.getPantry,
    staleTime: 5 * 60_000,
  });
}

// Whole-set replace with an optimistic cache write so chip add/remove/pin feels
// instant; roll back on error, refetch on settle to pick up server-derived
// categories + unmatched.
export function useUpdatePantry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: PantryItem[]) =>
      api.replacePantry({
        items: items.map((i) => ({
          ingredient: i.ingredient,
          is_staple: i.is_staple,
        })),
      }),
    onMutate: async (items) => {
      await qc.cancelQueries({ queryKey: queryKeys.pantry });
      const prev = qc.getQueryData<PantryResponse>(queryKeys.pantry);
      qc.setQueryData<PantryResponse>(queryKeys.pantry, {
        items: [...items].sort((a, b) => a.ingredient.localeCompare(b.ingredient)),
        unmatched: [],
      });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(queryKeys.pantry, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.pantry }),
  });
}
