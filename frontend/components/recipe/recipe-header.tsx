import { Clock3, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cuisineLabel, titleCase } from "@/lib/filter-options";
import type { RecipeDetail } from "@/types/api";

export function RecipeHeader({ recipe }: { recipe: RecipeDetail }) {
  const cuisine = recipe.region
    ? cuisineLabel(`${recipe.cuisine}/${recipe.region}`)
    : recipe.cuisine
      ? cuisineLabel(recipe.cuisine)
      : null;

  return (
    <header className="space-y-4">
      {recipe.image_url && (
        // themealdb images only; plain <img> sidesteps next/image remote config.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={recipe.image_url}
          alt={recipe.title}
          width={800}
          height={450}
          className="aspect-video w-full rounded-xl object-cover"
        />
      )}

      <div className="space-y-3">
        <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight">
          {recipe.title}
        </h1>
        {recipe.description && (
          <p className="text-muted-foreground">{recipe.description}</p>
        )}

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1 tabular">
            <Clock3 className="size-4" /> {recipe.time_minutes} min
          </span>
          <span className="inline-flex items-center gap-1 tabular">
            <Users className="size-4" /> serves {recipe.servings}
          </span>
          {cuisine && <Badge variant="primary">{cuisine}</Badge>}
          {recipe.diet_labels.map((d) => (
            <Badge key={d} variant="outline" className="font-normal">
              {titleCase(d.replace(/_/g, " "))}
            </Badge>
          ))}
          {recipe.allergens.map((a) => (
            <Badge key={a} variant="default" className="font-normal">
              contains {a}
            </Badge>
          ))}
        </div>
      </div>
    </header>
  );
}
