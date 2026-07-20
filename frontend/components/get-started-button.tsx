"use client";

import Link from "next/link";
import { signIn, useSession } from "next-auth/react";

const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

// The primary CTA. Signed in (or auth disabled in dev) → straight to /app.
// Signed out → open Google directly, skipping the interstitial /login page.
export function GetStartedButton({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  const { status } = useSession();

  if (authEnabled && status === "unauthenticated") {
    return (
      <button
        type="button"
        onClick={() => signIn("google", { callbackUrl: "/app" })}
        className={className}
      >
        {children}
      </button>
    );
  }

  return (
    <Link href="/app" className={className}>
      {children}
    </Link>
  );
}
