"use client";

import { useHealth } from "@/lib/hooks/use-health";
import { cn } from "@/lib/utils";

// Live backend status — doubles as the client->API (CORS) proof.
export function KitchenStatus() {
  const { data, isLoading, isError } = useHealth();
  const online = data?.status === "ok" && data.db && data.redis;
  const label = isLoading
    ? "Waking the kitchen…"
    : isError
      ? "Kitchen offline"
      : online
        ? "Kitchen online"
        : "Kitchen degraded";
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-2.5 py-1 text-sm text-muted-foreground backdrop-blur sm:px-3"
      // On phones the pill collapses to just the status dot to keep the header
      // uncrowded; the label returns from `sm` up. Keep the meaning for SRs.
      aria-label={label}
      title={label}
    >
      <span
        className={cn(
          "size-2 rounded-full",
          isLoading && "animate-pulse bg-turmeric",
          isError && "bg-chili",
          online && "bg-primary",
        )}
        aria-hidden
      />
      <span className="hidden sm:inline">{label}</span>
    </span>
  );
}
