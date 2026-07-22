"use client";

import { api } from "@/lib/api-client";

// A per-browser session id, persisted so events (and A/B variant assignment)
// stay stable across page loads/tabs.
const SESSION_KEY = "nourish:session";
let cachedSessionId: string | null = null;

export function getSessionId(): string {
  if (cachedSessionId) return cachedSessionId;
  if (typeof window === "undefined") return "server";
  try {
    let id = window.localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem(SESSION_KEY, id);
    }
    cachedSessionId = id;
    return id;
  } catch {
    return "unknown-session";
  }
}

// The most recent A/B variant this session was assigned (set after each
// recommend response). Tags subsequent events so they can be
// grouped by variant even though the event itself doesn't know about ranking.
let lastVariant: string | null = null;

export function setLastVariant(variant: string | null): void {
  lastVariant = variant;
}

// Fire-and-forget analytics. `props` may include `recipe_id` for a
// recipe-scoped event; it's lifted into the dedicated schema field.
export function track(name: string, props: Record<string, unknown> = {}): void {
  if (typeof window === "undefined") return;
  const { recipe_id, ...rest } = props as { recipe_id?: unknown };
  api
    .track({
      name,
      session_id: getSessionId(),
      recipe_id: typeof recipe_id === "number" ? recipe_id : null,
      variant: lastVariant,
      props: rest,
    })
    .catch(() => {
      /* analytics must never break the UI */
    });
}
