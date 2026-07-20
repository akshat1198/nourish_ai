export function StepsList({ steps }: { steps: string[] }) {
  if (steps.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-2xl font-semibold tracking-tight">Method</h2>
      <ol className="space-y-4">
        {steps.map((step, i) => (
          <li key={i} className="flex gap-4">
            <span className="tabular grid size-7 shrink-0 place-items-center rounded-full bg-primary/10 text-sm font-medium text-primary">
              {i + 1}
            </span>
            <p className="pt-0.5 leading-relaxed">{step}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
