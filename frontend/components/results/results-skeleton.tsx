"use client";

import { useEffect, useState } from "react";
import { Skeleton } from "@/components/ui/skeleton";

/** Past this, the request is slower than a plain corpus lookup. */
const SLOW_AFTER_MS = 2500;

/**
 * Loading state for the results list.
 *
 * Most requests are served from the corpus in well under a second. When
 * nothing fits the filters the backend writes recipes to order, which takes
 * several seconds — long enough that a silent spinner reads as a hang.
 *
 * The longer message is deliberately conditional. Recommendations are a single
 * request, so the client cannot know whether the backend decided to generate;
 * a slow lookup looks exactly like a generation from here. Stating "writing
 * you some recipes" outright was wrong often enough to matter — it appeared on
 * a Kenyan search that was served entirely from the corpus.
 */
export function ResultsSkeleton() {
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="space-y-4">
      <p
        className="text-sm text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        {slow
          ? "Still looking — if nothing in the collection fits, we'll write you one, which takes a few seconds…"
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
