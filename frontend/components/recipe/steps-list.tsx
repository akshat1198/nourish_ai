import { cn } from "@/lib/utils";

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
