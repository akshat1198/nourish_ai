"use client";

import { notFound, useParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { AvoidStep } from "@/components/filters/steps/avoid-step";
import { CuisineStep } from "@/components/filters/steps/cuisine-step";
import { DietStep } from "@/components/filters/steps/diet-step";
import { MealStep } from "@/components/filters/steps/meal-step";
import { MoreStep } from "@/components/filters/steps/more-step";
import { ReviewActions, ReviewBody } from "@/components/filters/review-page";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import {
  STEP_SLUGS,
  STEP_TITLES,
  isStepSlug,
  nextSlug,
  stepIndex,
  type StepSlug,
} from "@/lib/flow/steps";

const BODIES: Record<StepSlug, () => React.ReactElement> = {
  cuisine: CuisineStep,
  meal: MealStep,
  diet: DietStep,
  avoid: AvoidStep,
  more: MoreStep,
  review: ReviewBody,
};

export default function FilterStepPage() {
  const params = useParams();
  const raw = Array.isArray(params.step) ? params.step[0] : params.step;
  if (!isStepSlug(raw)) notFound();
  const slug = raw;

  const { ready, goBack, goNext } = useFilterFlow();
  const idx = stepIndex(slug);
  const Body = BODIES[slug];
  const isReview = slug === "review";
  // On the last filter step, the forward button leads to Review.
  const forwardLabel = nextSlug(slug) === "review" ? "Review" : "Next";

  return (
    <Card>
      <CardContent className="space-y-6 pt-5">
        {/* progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium uppercase tracking-wide">
              Tonight&apos;s recipe
            </span>
            <span className="tabular">
              Step {idx + 1} of {STEP_SLUGS.length}
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-300"
              style={{ width: `${((idx + 1) / STEP_SLUGS.length) * 100}%` }}
            />
          </div>
        </div>

        <h2 className="font-display text-2xl font-semibold tracking-tight">
          {STEP_TITLES[slug]}
        </h2>

        {/* body — a light skeleton until answers hydrate to avoid a flash of
            empty selections */}
        {ready ? (
          <Body />
        ) : (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24 rounded-full" />
            ))}
          </div>
        )}

        {/* footer nav */}
        <div className="flex items-center justify-between border-t border-border pt-5">
          <Button variant="ghost" onClick={goBack}>
            <ArrowLeft /> Back
          </Button>
          {isReview ? (
            <ReviewActions />
          ) : (
            <Button onClick={goNext}>
              {forwardLabel} <ArrowRight />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
