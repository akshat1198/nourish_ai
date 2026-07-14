"use client";

import { signIn } from "next-auth/react";
import { Button } from "@/components/ui/button";

const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

function GoogleIcon() {
  return (
    <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.2 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z"
      />
    </svg>
  );
}

export default function LoginPage() {
  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-6 text-center">
      <div className="pointer-events-none absolute inset-0 -z-10" aria-hidden>
        <div className="absolute -left-32 top-1/4 size-[32rem] rounded-full bg-primary/20 blur-3xl animate-aurora" />
        <div className="absolute -right-32 bottom-1/4 size-[28rem] rounded-full bg-turmeric/20 blur-3xl animate-aurora [animation-delay:-7s]" />
      </div>

      <span className="font-display text-3xl font-semibold tracking-tight">
        Nourish<span className="text-primary">AI</span>
      </span>
      <h1 className="mt-8 max-w-sm font-display text-4xl font-semibold leading-tight tracking-tight text-balance">
        Cook what you already have.
      </h1>
      <p className="mt-4 max-w-xs text-muted-foreground">
        Sign in to save your pantry and get recipes that fit what&apos;s in your
        kitchen.
      </p>

      <div className="mt-9 w-full max-w-xs">
        {authEnabled ? (
          <Button
            size="lg"
            variant="outline"
            className="w-full gap-3 bg-card"
            onClick={() => signIn("google", { callbackUrl: "/app" })}
          >
            <GoogleIcon />
            Continue with Google
          </Button>
        ) : (
          <p className="rounded-lg border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
            Google sign-in isn&apos;t set up yet. You can keep using the app in
            dev mode.
          </p>
        )}
      </div>
    </div>
  );
}
