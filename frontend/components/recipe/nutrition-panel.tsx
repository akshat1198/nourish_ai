import type { RecipeDetail } from "@/types/api";

const MACROS: { key: string; label: string; unit: string }[] = [
  { key: "calories", label: "Calories", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "carbs_g", label: "Carbs", unit: "g" },
  { key: "fat_g", label: "Fat", unit: "g" },
];

export function NutritionPanel({ recipe }: { recipe: RecipeDetail }) {
  const n = recipe.nutrition ?? {};
  const shown = MACROS.filter((m) => n[m.key] != null);
  if (shown.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline gap-2">
        <h2 className="font-display text-2xl font-semibold tracking-tight">
          Nutrition
        </h2>
        <span className="text-xs text-muted-foreground">per serving</span>
      </div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {shown.map((m) => (
          <div key={m.key} className="rounded-lg border border-border bg-card p-3">
            <dt className="text-xs text-muted-foreground">{m.label}</dt>
            <dd className="tabular mt-0.5 text-lg font-semibold">
              {Math.round(n[m.key])}
              <span className="ml-0.5 text-sm font-normal text-muted-foreground">
                {m.unit}
              </span>
            </dd>
          </div>
        ))}
      </dl>
      {recipe.nutrition_estimated && (
        <p className="text-xs text-muted-foreground">
          Estimated from ingredients — treat as a rough guide.
        </p>
      )}
    </section>
  );
}
