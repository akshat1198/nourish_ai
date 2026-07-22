"use client";

import { Bookmark } from "lucide-react";
import { useToggleSave } from "@/lib/hooks/use-saved";
import { cn } from "@/lib/utils";
import type { RecipeSummary } from "@/types/api";

// Bookmark toggle backed by the saved list. Two looks: a full pill ("Save" /
// "Saved") for the detail action bar, and an icon-only chip for result cards.
export function SaveButton({
  summary,
  variant = "pill",
  className,
}: {
  summary: RecipeSummary;
  variant?: "pill" | "icon";
  className?: string;
}) {
  const { saved, toggle, pending } = useToggleSave(summary);
  const icon = (
    <Bookmark className={cn("size-4", saved && "fill-current")} />
  );

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={() => toggle()}
        disabled={pending}
        aria-pressed={saved}
        aria-label={saved ? "Remove from saved" : "Save recipe"}
        className={cn(
          "grid size-9 shrink-0 touch-manipulation place-items-center rounded-full border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          saved
            ? "border-primary bg-primary/10 text-primary"
            : "border-border bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
          className,
        )}
      >
        {icon}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => toggle()}
      disabled={pending}
      aria-pressed={saved}
      className={cn(
        "inline-flex h-9 touch-manipulation items-center justify-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        saved
          ? "border-primary bg-primary/10 text-primary"
          : "border-border bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
        className,
      )}
    >
      {icon}
      {saved ? "Saved" : "Save"}
    </button>
  );
}
