"use client";

import { LogOut } from "lucide-react";
import { signIn, signOut, useSession } from "next-auth/react";
import { Button } from "@/components/ui/button";

const authEnabled = process.env.NEXT_PUBLIC_AUTH_ENABLED === "true";

export function UserMenu() {
  const { data, status } = useSession();

  // In dev (auth not configured) there's nothing to sign into — stay invisible.
  if (!authEnabled || status === "loading") return null;

  if (!data?.user) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => signIn("google", { callbackUrl: "/app" })}
      >
        Sign in
      </Button>
    );
  }

  const name = data.user.name ?? data.user.email ?? "You";
  const initial = name.charAt(0).toUpperCase();

  return (
    <div className="flex items-center gap-2.5">
      {data.user.image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={data.user.image}
          alt=""
          width={28}
          height={28}
          className="size-7 rounded-full"
          referrerPolicy="no-referrer"
        />
      ) : (
        <span className="grid size-7 place-items-center rounded-full bg-primary/15 text-xs font-medium text-primary">
          {initial}
        </span>
      )}
      <button
        type="button"
        onClick={() => signOut({ callbackUrl: "/" })}
        aria-label="Sign out"
        className="relative inline-flex touch-manipulation items-center gap-1 text-sm text-muted-foreground before:absolute before:left-1/2 before:top-1/2 before:size-9 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] hover:text-foreground sm:before:hidden"
      >
        <LogOut className="size-3.5" />
        <span className="hidden sm:inline">Sign out</span>
      </button>
    </div>
  );
}
