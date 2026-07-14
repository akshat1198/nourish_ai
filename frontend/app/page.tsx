"use client";

import { ArrowRight, Clock3, Leaf } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useHealth } from "@/lib/hooks/use-health";
import { cn } from "@/lib/utils";

function KitchenStatus() {
  const { data, isLoading, isError } = useHealth();
  const online = data?.status === "ok" && data.db && data.redis;
  const label = isLoading
    ? "Waking the kitchen…"
    : isError
      ? "Kitchen offline"
      : online
        ? "Kitchen online"
        : "Kitchen degraded";
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
      <span
        className={cn(
          "size-2 rounded-full",
          isLoading && "animate-pulse bg-turmeric",
          isError && "bg-chili",
          online && "bg-primary",
        )}
        aria-hidden
      />
      {label}
    </span>
  );
}

function MatchMeter({ have, total }: { have: number; total: number }) {
  return (
    <span className="inline-flex items-center gap-1" aria-label={`${have} of ${total} key ingredients on hand`}>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "size-1.5 rounded-full",
            i < have ? "bg-primary" : "border border-cardamom",
          )}
        />
      ))}
    </span>
  );
}

export default function Home() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col px-5">
      {/* Header */}
      <header className="flex items-center justify-between py-5">
        <span className="font-display text-2xl font-semibold tracking-tight">
          Nourish<span className="text-primary">AI</span>
        </span>
        <KitchenStatus />
      </header>

      {/* Hero — the thesis: what you have becomes what you cook */}
      <main className="flex flex-1 flex-col justify-center py-10">
        <p className="mb-4 inline-flex w-fit items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <Leaf className="size-3.5" />
          Pantry-first cooking
        </p>

        <h1 className="font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
          Cook what you
          <br />
          <span className="text-primary">already have.</span>
        </h1>

        <p className="mt-5 max-w-md text-lg leading-relaxed text-muted-foreground">
          Keep your pantry current, tell us the mood — cuisine, meal, how you want
          to eat — and get recipes you can actually make tonight.
        </p>

        {/* Signature: ingredient tokens transforming into a recipe */}
        <div className="mt-10 flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex flex-wrap gap-2">
            <IngredientToken name="paneer" category="dairy" staple />
            <IngredientToken name="tomato" category="veg" />
            <IngredientToken name="cumin" category="spice" />
            <IngredientToken name="basmati rice" category="grain" staple />
          </div>

          <ArrowRight className="hidden size-5 shrink-0 text-muted-foreground sm:block" aria-hidden />

          <Card className="w-full max-w-xs shrink-0 p-4 sm:w-auto">
            <div className="flex items-start justify-between gap-3">
              <h3 className="font-display text-lg font-medium leading-snug">
                Paneer Jeera Rice
              </h3>
              <Badge variant="primary">Gujarati</Badge>
            </div>
            <div className="mt-3 flex items-center gap-3 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1 tabular">
                <Clock3 className="size-3.5" /> 25 min
              </span>
              <span className="tabular">18g protein</span>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <MatchMeter have={3} total={4} />
              <span>3 of 4 on hand</span>
            </div>
          </Card>
        </div>

        <div className="mt-10">
          <Button size="lg" disabled className="cursor-not-allowed opacity-60">
            Set up my pantry
            <ArrowRight />
          </Button>
          <p className="mt-2 text-sm text-muted-foreground">
            Pantry, preferences, and recipes arrive next.
          </p>
        </div>
      </main>

      {/* The flow — the real three steps, not decoration */}
      <footer className="border-t border-border py-5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Pantry</span>
          <ArrowRight className="size-3.5" aria-hidden />
          <span className="font-medium text-foreground">Preferences</span>
          <ArrowRight className="size-3.5" aria-hidden />
          <span className="font-medium text-foreground">Recipes</span>
          <span className="ml-auto text-xs">Foundation · Stage 5.2</span>
        </div>
      </footer>
    </div>
  );
}
