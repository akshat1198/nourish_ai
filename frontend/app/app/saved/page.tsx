"use client";

import Link from "next/link";
import { Bookmark } from "lucide-react";
import { SaveButton } from "@/components/recipe/save-button";
import { SummaryCard } from "@/components/recipe/summary-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useSaved } from "@/lib/hooks/use-saved";
import { cn } from "@/lib/utils";

export default function SavedPage() {
  const { data, isLoading, isError, refetch } = useSaved();
  const recipes = data?.recipes ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-4xl font-semibold tracking-tight">
          Saved recipes
        </h1>
        <p className="mt-2 text-muted-foreground">
          Recipes you bookmarked — ready when you are.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[88px] w-full rounded-xl" />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex items-center justify-between rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
          <span className="text-destructive">Couldn&apos;t load your saved recipes.</span>
          <Button size="sm" variant="outline" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      )}

      {!isLoading && !isError && recipes.length === 0 && (
        <div className="rounded-xl border border-dashed border-border py-12 text-center">
          <Bookmark className="mx-auto size-6 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            Nothing saved yet. Tap the bookmark on any recipe to keep it here.
          </p>
          <Link
            href="/app"
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-4")}
          >
            Find recipes
          </Link>
        </div>
      )}

      {recipes.length > 0 && (
        <div className="space-y-2">
          {recipes.map((r) => (
            <SummaryCard
              key={r.id}
              recipe={r}
              action={<SaveButton variant="icon" summary={r} />}
            />
          ))}
        </div>
      )}
    </div>
  );
}
