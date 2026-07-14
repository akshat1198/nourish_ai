"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { setSession } from "@/lib/auth-token";

// Keeps the module-level auth holder in step with the session so the fetch
// wrapper always sends the right bearer / identity.
export function AuthTokenSync() {
  const { data } = useSession();
  useEffect(() => {
    setSession(data?.apiToken, data?.user?.id);
  }, [data]);
  return null;
}
