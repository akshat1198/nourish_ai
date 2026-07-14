// The `authorized` callback in auth.ts decides access; it no-ops until Google is
// configured, so dev (X-User-Key) keeps working. Only /app is gated.
export { auth as middleware } from "@/auth";

export const config = {
  matcher: ["/app/:path*"],
};
