"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { Plan } from "@/types/api";

export function usePlans() {
  return useQuery({
    queryKey: queryKeys.plans,
    queryFn: api.getPlans,
    staleTime: 30_000,
  });
}

export function usePlan(id: number) {
  return useQuery({
    queryKey: queryKeys.plan(id),
    queryFn: () => api.getPlan(id),
    staleTime: 30_000,
  });
}

export function useCreatePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.createPlan(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plans }),
  });
}

export function useDeletePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deletePlan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.plans }),
  });
}

// The item endpoints return the full updated plan, so cache it directly and
// refresh the list (item counts) + the shopping list.
export function useAddPlanItem(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ recipeId, slot }: { recipeId: number; slot?: string | null }) =>
      api.addPlanItem(planId, recipeId, slot),
    onSuccess: (plan: Plan) => {
      qc.setQueryData(queryKeys.plan(planId), plan);
      qc.invalidateQueries({ queryKey: queryKeys.plans });
      qc.invalidateQueries({ queryKey: queryKeys.planShopping(planId) });
    },
  });
}

export function useRemovePlanItem(planId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (recipeId: number) => api.removePlanItem(planId, recipeId),
    onSuccess: (plan: Plan) => {
      qc.setQueryData(queryKeys.plan(planId), plan);
      qc.invalidateQueries({ queryKey: queryKeys.plans });
      qc.invalidateQueries({ queryKey: queryKeys.planShopping(planId) });
    },
  });
}

export function usePlanShoppingList(planId: number, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.planShopping(planId),
    queryFn: () => api.getPlanShoppingList(planId),
    enabled,
    staleTime: 30_000,
  });
}
