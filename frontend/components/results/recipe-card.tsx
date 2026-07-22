import Link from "next/link";
import { Clock3, Trophy } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { MatchMeter } from "@/components/match-meter";
import { SaveButton } from "@/components/recipe/save-button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cuisineLabel, titleCase } from "@/lib/filter-options";
import { cn } from "@/lib/utils";
import type { RankedRecipe } from "@/types/api";

function num(n: number | undefined) {
  return n == null ? null : Math.round(n);
}

export function RecipeCard({
  recipe,
  top = false,
}: {
  recipe: RankedRecipe;
  top?: boolean;
}) {
  const have = recipe.matched_ingredients.length;
  const total = have + recipe.missing_ingredients.length;
  const cuisine = recipe.region
    ? cuisineLabel(`${recipe.cuisine}/${recipe.region}`)
    : recipe.cuisine
      ? cuisineLabel(recipe.cuisine)
      : null;
  const protein = num(recipe.nutrition?.protein_g);
  const calories = num(recipe.nutrition?.calories);

  return (
    <Card
      className={cn(
        "p-5 transition-shadow hover:shadow-md",
        top && "border-primary/40 ring-1 ring-primary/20",
      )}
    >
      {top && (
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">
          <Trophy className="size-3.5" />
          Top match
        </div>
      )}
      <div className="flex items-start justify-between gap-3">
        <Link
          href={`/recipes/${recipe.id}`}
          className="font-display text-xl font-semibold leading-snug hover:underline"
        >
          {recipe.title}
        </Link>
        <div className="flex shrink-0 items-center gap-2">
          {cuisine && <Badge variant="primary">{cuisine}</Badge>}
          <SaveButton
            variant="icon"
            summary={{
              id: recipe.id,
              title: recipe.title,
              time_minutes: recipe.time_minutes,
              cuisine: recipe.cuisine,
              region: recipe.region,
            }}
          />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1 tabular">
          <Clock3 className="size-3.5" /> {recipe.time_minutes} min
        </span>
        {protein != null && <span className="tabular">{protein}g protein</span>}
        {calories != null && <span className="tabular">{calories} kcal</span>}
        {recipe.diet_labels.slice(0, 3).map((d) => (
          <Badge key={d} variant="outline" className="font-normal">
            {titleCase(d.replace("_", " "))}
          </Badge>
        ))}
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{recipe.why}</p>

      {total > 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <MatchMeter have={have} total={total} />
          <span className="tabular">
            {have} of {total} ingredients on hand
          </span>
        </div>
      )}

      {recipe.missing_ingredients.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs uppercase tracking-wide text-muted-foreground">
            You&apos;ll need
          </p>
          <div className="flex flex-wrap gap-1.5">
            {recipe.missing_ingredients.map((m) => (
              <IngredientToken key={m} name={m} muted />
            ))}
          </div>
        </div>
      )}

      {recipe.substitutions.length > 0 && (
        <div className="mt-3 space-y-1 rounded-lg bg-secondary/40 p-3">
          {recipe.substitutions.map((s, i) => (
            <p key={i} className="text-xs text-muted-foreground">
              <span className="font-medium text-primary">Swap:</span> use {s.use}{" "}
              for {s.missing}{" "}
              <span className="text-muted-foreground/70">({s.ratio})</span>
            </p>
          ))}
        </div>
      )}
    </Card>
  );
}
