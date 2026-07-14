// Bridges the Auth.js session (client) to the plain fetch wrapper. AuthTokenSync
// pushes the current bearer + identity here on every session change; apiFetch
// and the profile path read from it. No token yet => dev X-User-Key identity.

const DEV_USER_KEY = process.env.NEXT_PUBLIC_DEV_USER_KEY ?? "dev-user";

let authToken: string | null = null;
let userKey: string = DEV_USER_KEY;

export function setSession(
  token: string | null | undefined,
  googleId: string | null | undefined,
): void {
  authToken = token ?? null;
  userKey = googleId ? `google:${googleId}` : DEV_USER_KEY;
}

export function getAuthToken(): string | null {
  return authToken;
}

export function getUserKey(): string {
  return userKey;
}
