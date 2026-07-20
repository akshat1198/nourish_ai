"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";
import { AttributionFooter } from "@/components/recipe/attribution-footer";
import { IngredientsPanel } from "@/components/recipe/ingredients-panel";
import { ModifiedBanner } from "@/components/recipe/modified-banner";
import { NutritionPanel } from "@/components/recipe/nutrition-panel";
import { RecipeHeader } from "@/components/recipe/recipe-header";
import { StepsList } from "@/components/recipe/steps-list";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useModifyRecipe } from "@/lib/hooks/use-modify-recipe";
import { useRecipe } from "@/lib/hooks/use-recipe";
import type { ModifyResponse } from "@/types/api";

function BackLink() {
  return (
    <Link
      href="/app"
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="size-4" /> Back to your kitchen
    </Link>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 px-6 py-10">
      <BackLink />
      {children}
    </div>
  );
}

export function RecipeDetailView({ id }: { id: number }) {
  const { data: recipe, isLoading, isError, error, refetch } = useRecipe(id);
  // Serving override (null = the recipe's own servings). Reset on navigation.
  const [servingsOverride, setServingsOverride] = useState<number | null>(null);
  // Applied ingredient swap (null = original). One active swap at a time.
  const [modified, setModified] = useState<ModifyResponse | null>(null);
  const modify = useModifyRecipe(id);
  useEffect(() => {
    setServingsOverride(null);
    setModified(null);
  }, [id]);

  const applySwap = (from: string, to: string) =>
    modify.mutate(
      { from_ingredient: from, to_ingredient: to },
      { onSuccess: setModified },
    );

  if (isLoading) {
    return (
      <Shell>
        <div className="space-y-4">
          <Skeleton className="h-10 w-2/3 rounded-lg" />
          <Skeleton className="h-4 w-full rounded" />
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      </Shell>
    );
  }

  if (isError) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <Shell>
        <div className="space-y-3 py-8">
          <h1 className="font-display text-3xl font-semibold tracking-tight">
            {notFound ? "Recipe not found" : "Couldn't load this recipe"}
          </h1>
          <p className="text-muted-foreground">
            {notFound
              ? "This recipe may have been removed. Head back and keep exploring."
              : "Something went wrong fetching this recipe."}
          </p>
          {!notFound && (
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              Retry
            </Button>
          )}
        </div>
      </Shell>
    );
  }

  if (!recipe) return null;

  const servings = servingsOverride ?? recipe.servings;
  const ingredients = modified?.ingredients ?? recipe.ingredients;
  const steps = modified?.steps ?? recipe.steps;

  return (
    <Shell>
      <RecipeHeader recipe={recipe} />

      {modified && (
        <ModifiedBanner modified={modified} onReset={() => setModified(null)} />
      )}
      {modify.isPending && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Adjusting the recipe…
        </p>
      )}
      {modify.isError && (
        <p className="text-sm text-destructive">
          Couldn&apos;t apply that swap. Try another.
        </p>
      )}

      <IngredientsPanel
        ingredients={ingredients}
        servings={servings}
        baseServings={recipe.servings}
        onServings={setServingsOverride}
        onSwap={applySwap}
        pendingSwap={modify.isPending}
      />
      <StepsList
        steps={steps}
        changedIndexes={modified?.changed_step_indexes ?? []}
      />
      <NutritionPanel recipe={recipe} />
      <AttributionFooter recipe={recipe} />
    </Shell>
  );
}
