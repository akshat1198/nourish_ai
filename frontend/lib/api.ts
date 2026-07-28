// Typed fetch wrapper. Talks directly to the CORS-enabled FastAPI backend.
//
// Dev identity via the X-User-Key header (backend AUTH_MODE=disabled).
// Swaps in an Authorization: Bearer token from the Auth.js session once signed in.

import { getAuthToken, getUserKey } from "@/lib/auth-token";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  // FormData sets its own multipart Content-Type with a boundary; overriding
  // it with JSON makes the body unparseable server-side.
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  // Signed in -> verified bearer; otherwise the dev X-User-Key identity.
  const token = getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  } else if (!headers.has("Authorization")) {
    headers.set("X-User-Key", getUserKey());
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
