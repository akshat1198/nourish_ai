import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { SignJWT } from "jose";

// Auth is "configured" only once a Google client id is present. Until then the
// app runs in dev mode (X-User-Key) and nothing is locked behind sign-in.
const authConfigured = !!process.env.AUTH_GOOGLE_ID;
const sharedSecret = new TextEncoder().encode(process.env.AUTH_SHARED_SECRET ?? "");

const API_TOKEN_TTL = 24 * 60 * 60; // 24h
const REMINT_BEFORE = 12 * 60 * 60; // re-mint when < 12h remains

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: authConfigured ? [Google] : [],
  callbacks: {
    async jwt({ token, profile }) {
      if (profile?.sub) {
        token.sub = profile.sub;
        token.email = profile.email ?? token.email;
        token.name = profile.name ?? token.name;
      }
      const now = Math.floor(Date.now() / 1000);
      const needsMint =
        token.sub &&
        process.env.AUTH_SHARED_SECRET &&
        (!token.apiToken ||
          !token.apiExp ||
          now > (token.apiExp as number) - REMINT_BEFORE);
      if (needsMint) {
        const exp = now + API_TOKEN_TTL;
        // HS256 bearer the FastAPI backend verifies (iss/aud/sub must match
        // AUTH_JWT_ISS / AUTH_JWT_AUD). jose is Edge-safe (runs in middleware).
        token.apiToken = await new SignJWT({
          email: token.email,
          name: token.name,
        })
          .setProtectedHeader({ alg: "HS256" })
          .setSubject(token.sub as string)
          .setIssuer("nourish-web")
          .setAudience("nourish-api")
          .setIssuedAt(now)
          .setExpirationTime(exp)
          .sign(sharedSecret);
        token.apiExp = exp;
      }
      return token;
    },
    async session({ session, token }) {
      session.apiToken = token.apiToken as string | undefined;
      if (session.user) session.user.id = token.sub as string;
      return session;
    },
    authorized({ auth, request }) {
      if (!authConfigured) return true; // not set up yet — don't lock anyone out
      const onApp = request.nextUrl.pathname.startsWith("/app");
      if (onApp) return !!auth?.user;
      return true;
    },
  },
});
