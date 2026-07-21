import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// WS6: shown while a recipe's method is being enriched on first view — a few
// numbered step rows shimmer in, so the page feels like it's coming to life.
export function MethodSkeleton({ count = 6 }: { count?: number }) {
  const rows = Math.min(Math.max(count, 4), 9);
  return (
    <section className="space-y-3" aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-2.5">
        <h2 className="font-display text-2xl font-semibold tracking-tight">Method</h2>
        <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" /> writing it up…
        </span>
      </div>
      <ol className="space-y-4">
        {Array.from({ length: rows }).map((_, i) => (
          <li key={i} className="flex gap-4">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-medium text-primary/40">
              {i + 1}
            </span>
            <div className="flex-1 space-y-2 pt-1.5">
              <Skeleton className="h-3 w-full rounded" />
              <Skeleton className={cn("h-3 rounded", i % 3 === 0 ? "w-[70%]" : "w-[88%]")} />
              {i % 2 === 0 && <Skeleton className="h-3 w-[55%] rounded" />}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function StepsList({
  steps,
  changedIndexes = [],
}: {
  steps: string[];
  changedIndexes?: number[];
}) {
  if (steps.length === 0) return null;
  const changed = new Set(changedIndexes);

  return (
    <section className="space-y-3">
      <h2 className="font-display text-2xl font-semibold tracking-tight">Method</h2>
      <ol className="space-y-4">
        {steps.map((step, i) => {
          const isChanged = changed.has(i);
          return (
            <li key={i} className="flex gap-4">
              <span
                className={cn(
                  "tabular grid size-7 shrink-0 place-items-center rounded-full text-sm font-medium",
                  isChanged
                    ? "bg-primary text-primary-foreground"
                    : "bg-primary/10 text-primary",
                )}
              >
                {i + 1}
              </span>
              <div
                className={cn(
                  "flex-1 pt-0.5",
                  isChanged &&
                    "-my-1 rounded-lg border-l-2 border-primary bg-primary/5 py-1 pl-3",
                )}
              >
                <p className="leading-relaxed">{step}</p>
                {isChanged && (
                  <span className="mt-1.5 inline-block rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-primary">
                    updated
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
