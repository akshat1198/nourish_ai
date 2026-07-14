"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { ProfileUpdate } from "@/types/api";

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: api.getProfile,
    staleTime: Infinity,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdate) => api.putProfile(body),
    onSuccess: (data) => qc.setQueryData(queryKeys.profile, data),
  });
}
