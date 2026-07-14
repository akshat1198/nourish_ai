// Typed fetch wrapper. Talks directly to the CORS-enabled FastAPI backend.
//
// Stage 5.2-5.4: dev identity via the X-User-Key header (backend AUTH_MODE=disabled).
// Stage 5.5 swaps in an Authorization: Bearer token from the Auth.js session.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEV_USER_KEY = process.env.NEXT_PUBLIC_DEV_USER_KEY;

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
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (DEV_USER_KEY && !headers.has("Authorization")) {
    headers.set("X-User-Key", DEV_USER_KEY);
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
