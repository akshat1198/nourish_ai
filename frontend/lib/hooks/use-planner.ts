"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { PlannerRequest, PlannerResponse } from "@/types/api";

// A mutation, not a query, and deliberately so: each run costs real money and
// takes ~7s, so it must never be refetched on focus, retried on mount, or
// deduped into a cache the way `use-recommendations` wants to be.
export function usePlanner() {
  return useMutation<PlannerResponse, Error, PlannerRequest>({
    mutationFn: (req) => api.plan(req),
    retry: false,
  });
}

/** Stable per-browser id so a follow-up question continues the same thread.
 *
 * The backend namespaces this with the authenticated identity before it
 * reaches the checkpoint, so it is an opaque conversation handle, not a
 * credential — two people cannot collide by choosing the same value.
 */
export function getPlannerSessionId(): string {
  const KEY = "nourish.planner.session";
  try {
    const existing = window.localStorage.getItem(KEY);
    if (existing) return existing;
    const fresh = crypto.randomUUID();
    window.localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    // Private browsing or blocked storage: a per-load id still works, it just
    // will not survive a refresh.
    return crypto.randomUUID();
  }
}
