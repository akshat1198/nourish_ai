import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cuisineLabel } from "@/lib/filter-options";
import type { RecipeSummary } from "@/types/api";

// Compact recipe card for the Saved list and meal-plan items. `action` is an
// optional control (save toggle, remove-from-plan) rendered top-right.
export function SummaryCard({
  recipe,
  action,
}: {
  recipe: RecipeSummary;
  action?: React.ReactNode;
}) {
  const cuisine = recipe.region
    ? cuisineLabel(`${recipe.cuisine}/${recipe.region}`)
    : recipe.cuisine
      ? cuisineLabel(recipe.cuisine)
      : null;

  return (
    <Card className="flex items-center gap-3 p-3 transition-shadow hover:shadow-md">
      {recipe.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={recipe.image_url}
          alt=""
          className="size-16 shrink-0 rounded-lg object-cover"
        />
      )}
      <div className="min-w-0 flex-1">
        <Link
          href={`/recipes/${recipe.id}`}
          className="font-display text-base font-semibold leading-snug hover:underline"
        >
          {recipe.title}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          {cuisine && (
            <Badge variant="primary" className="text-[11px]">
              {cuisine}
            </Badge>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </Card>
  );
}
