import { DOT_COLOR, type IngredientCategory } from "@/components/ingredient-token";
import { cn } from "@/lib/utils";

// Subtle key for the category dots so the color-coding is discoverable.
const LEGEND: { cat: IngredientCategory; label: string }[] = [
  { cat: "protein", label: "Protein" },
  { cat: "veg", label: "Veg" },
  { cat: "grain", label: "Grain" },
  { cat: "spice", label: "Spice" },
  { cat: "dairy", label: "Dairy" },
  { cat: "fruit", label: "Fruit" },
  { cat: "other", label: "Other" },
];

export function IngredientLegend({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1.5", className)}>
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Groups
      </span>
      {LEGEND.map(({ cat, label }) => (
        <span
          key={cat}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
        >
          <span className={cn("size-2 rounded-full", DOT_COLOR[cat])} aria-hidden />
          {label}
        </span>
      ))}
    </div>
  );
}
