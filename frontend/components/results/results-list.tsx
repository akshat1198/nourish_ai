"use client";

import { ModeBanner } from "@/components/results/mode-banner";
import { RecipeCard } from "@/components/results/recipe-card";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRecommendations } from "@/lib/hooks/use-recommendations";
import type { RecommendRequest } from "@/types/api";

export function ResultsList({ request }: { request: RecommendRequest | null }) {
  const { data, isLoading, isError, refetch } = useRecommendations(request);

  if (request === null) return null;

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-44 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <Card className="flex items-center justify-between p-5">
        <span className="text-sm text-destructive">
          Couldn&apos;t fetch recipes.
        </span>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </Card>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">
            Recipes for you
          </h2>
          {data.results.length > 0 && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              Ranked by best match — start from the top.
            </p>
          )}
        </div>
        <span className="tabular text-sm text-muted-foreground">
          {data.results.length} found
        </span>
      </div>

      <ModeBanner mode={data.mode} explanation={data.explanation} />

      {data.unmatched_pantry.length > 0 && (
        <p className="text-xs text-muted-foreground">
          We didn&apos;t recognise: {data.unmatched_pantry.join(", ")}
        </p>
      )}

      {data.results.length === 0 ? (
        <Card className="border-dashed bg-transparent p-8 text-center text-sm text-muted-foreground">
          No recipes matched those filters yet.
          {data.explanation
            ? ` ${data.explanation}`
            : " Try loosening a constraint — or a broader cuisine."}
        </Card>
      ) : (
        <div className="space-y-4">
          {data.results.map((r, i) => (
            <RecipeCard key={r.id} recipe={r} top={i === 0} />
          ))}
          {data.results.length < 10 && (
            <p className="pt-1 text-center text-sm text-muted-foreground">
              That&apos;s every match for these filters. For more to choose from,
              pick a broader cuisine or add a few more pantry ingredients.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
