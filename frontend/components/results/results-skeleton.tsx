"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";

/** After this long, the wait is almost certainly a recipe being written. */
const WRITING_AFTER_MS = 2500;

/**
 * Loading state for the results list.
 *
 * Most requests are served from the corpus in well under a second. When
 * nothing fits the filters the backend writes recipes to order, which takes
 * several seconds — long enough that a silent spinner reads as a hang. So the
 * copy changes once the wait passes the point where retrieval would have
 * answered, and says what is actually happening.
 */
export function ResultsSkeleton() {
  const [writing, setWriting] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setWriting(true), WRITING_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="space-y-4">
      <p
        className="text-sm text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        {writing
          ? "Nothing in the collection fits those filters — writing you some recipes…"
          : "Finding recipes…"}
      </p>

      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="space-y-3 rounded-xl border border-border bg-card p-5"
          aria-hidden="true"
        >
          <div className="flex items-start justify-between gap-3">
            <Skeleton className="h-6 w-1/2" />
            <Skeleton className="size-9 shrink-0 rounded-full" />
          </div>
          <div className="flex gap-3">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-4 w-4/5" />
          <div className="flex gap-1.5 pt-1">
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-16 rounded-full" />
            <Skeleton className="h-6 w-24 rounded-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
