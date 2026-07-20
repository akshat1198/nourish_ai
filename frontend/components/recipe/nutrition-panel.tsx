const MACROS: { key: string; label: string; unit: string }[] = [
  { key: "calories", label: "Calories", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "carbs_g", label: "Carbs", unit: "g" },
  { key: "fat_g", label: "Fat", unit: "g" },
];

function deltaLabel(d: number): string {
  const rounded = Math.round(d);
  if (rounded === 0) return "±0";
  return rounded > 0 ? `+${rounded}` : `${rounded}`;
}

export function NutritionPanel({
  nutrition,
  estimated,
  delta,
}: {
  nutrition: Record<string, number>;
  estimated: boolean;
  // Signed per-macro change from a swap; when present the figures are
  // post-swap estimates.
  delta?: Record<string, number>;
}) {
  const n = nutrition ?? {};
  const shown = MACROS.filter((m) => n[m.key] != null);
  if (shown.length === 0) return null;

  const swapped = delta != null;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline gap-2">
        <h2 className="font-display text-2xl font-semibold tracking-tight">
          Nutrition
        </h2>
        <span className="text-xs text-muted-foreground">per serving</span>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {shown.map((m) => {
          const d = delta?.[m.key];
          return (
            <div
              key={m.key}
              className="rounded-lg border border-border bg-card p-3"
            >
              <dt className="text-xs text-muted-foreground">{m.label}</dt>
              <dd className="tabular mt-0.5 text-lg font-semibold">
                {Math.round(n[m.key])}
                <span className="ml-0.5 text-sm font-normal text-muted-foreground">
                  {m.unit}
                </span>
              </dd>
              {d != null && Math.round(d) !== 0 && (
                <span className="tabular mt-0.5 inline-block text-xs text-muted-foreground">
                  {deltaLabel(d)} {m.unit} from swap
                </span>
              )}
            </div>
          );
        })}
      </dl>
      {(swapped || estimated) && (
        <p className="text-xs text-muted-foreground">
          {swapped
            ? "Estimated for your swap — treat as a rough guide."
            : "Estimated from ingredients — treat as a rough guide."}
        </p>
      )}
    </section>
  );
}
