"use client";

import { useEffect, useState } from "react";
import { ModeBanner } from "@/components/results/mode-banner";
import { RecipeCard } from "@/components/results/recipe-card";
import { ResultsSkeleton } from "@/components/results/results-skeleton";
import { Reveal } from "@/components/reveal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cuisineLabel } from "@/lib/filter-options";
import { useRecommendations } from "@/lib/hooks/use-recommendations";
import { setLastVariant, track } from "@/lib/track";
import type { RecommendRequest } from "@/types/api";

export function ResultsList({ request }: { request: RecommendRequest | null }) {
  const { data, isLoading, isError, refetch } = useRecommendations(request);
  // Dismissed cards drop out of THIS view only (not a persisted "hidden"
  // list) — the negative signal itself is recorded server-side by the card's
  // feedback call; refreshing/re-running the search brings a fresh list.
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!data) return;
    setLastVariant(data.variant); // tag subsequent events with this variant
    track("results_shown", { count: data.results.length, mode: data.mode });
    setDismissedIds(new Set()); // a fresh result set starts with nothing dismissed
  }, [data]);

  if (request === null) return null;

  if (isLoading) return <ResultsSkeleton />;

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

  const visibleResults = data.results.filter((r) => !dismissedIds.has(r.id));
  const allDismissed = data.results.length > 0 && visibleResults.length === 0;
  // The backend already ranks in-cuisine results above off-cuisine ones; this
  // only splits them so the divider can sit between the two groups.
  const inCuisine = visibleResults.filter((r) => r.cuisine_matched);
  const offCuisine = visibleResults.filter((r) => !r.cuisine_matched);
  const requestedCuisine =
    request.cuisines.length === 1 ? cuisineLabel(request.cuisines[0]) : null;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="font-display text-2xl font-semibold tracking-tight">
            Recipes for you
          </h2>
          {visibleResults.length > 0 && (
            <p className="mt-0.5 text-sm text-muted-foreground">
              Ranked by best match — start from the top.
            </p>
          )}
        </div>
        <span
          className="tabular text-sm text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          {visibleResults.length} found
        </span>
      </div>

      <ModeBanner mode={data.mode} explanation={data.explanation} />

      {data.unmatched_pantry.length > 0 && (
        <p className="text-xs text-muted-foreground">
          We didn&apos;t recognise: {data.unmatched_pantry.join(", ")}
        </p>
      )}

      {allDismissed ? (
        <Card className="border-dashed bg-transparent p-8 text-center text-sm text-muted-foreground">
          You&apos;ve dismissed every match for these filters. Try refining
          them for a different set.
        </Card>
      ) : visibleResults.length === 0 ? (
        <Card className="border-dashed bg-transparent p-8 text-center text-sm text-muted-foreground">
          No recipes matched those filters yet.
          {data.explanation
            ? ` ${data.explanation}`
            : " Try loosening a constraint — or a broader cuisine."}
        </Card>
      ) : (
        <div className="space-y-4">
          {inCuisine.map((r, i) => (
            <Reveal key={r.id} delay={Math.min(i, 6) * 60}>
              <RecipeCard
                recipe={r}
                top={i === 0}
                onDismiss={(id) =>
                  setDismissedIds((prev) => new Set(prev).add(id))
                }
              />
            </Reveal>
          ))}

          {/* Off-cuisine results are never blended into the list above. They
              sit behind their own heading so picking Thai and being shown
              Italian reads as an explicit fallback, not a broken filter. */}
          {offCuisine.length > 0 && (
            <div className="space-y-4 pt-2">
              {/* A real heading, not a styled separator: this is a distinct
                  group and screen-reader users should be able to navigate to
                  it under the "Recipes for you" h2. */}
              <div className="flex items-center gap-3">
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
                <h3 className="text-xs uppercase tracking-wide text-muted-foreground">
                  {requestedCuisine
                    ? `Not ${requestedCuisine}, but you could make these`
                    : "Outside your chosen cuisine"}
                </h3>
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
              </div>
              {offCuisine.map((r, i) => (
                <Reveal key={r.id} delay={Math.min(i, 6) * 60}>
                  <RecipeCard
                    recipe={r}
                    onDismiss={(id) =>
                      setDismissedIds((prev) => new Set(prev).add(id))
                    }
                  />
                </Reveal>
              ))}
            </div>
          )}

          {visibleResults.length < 10 && (
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
