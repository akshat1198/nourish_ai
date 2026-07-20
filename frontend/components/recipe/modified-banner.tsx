"use client";

import { Info, RotateCcw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ModifyResponse } from "@/types/api";

// The safety-facing summary of an applied swap: what it did to the allergen
// profile, plus the knock-on effects the cook should know before starting.
export function ModifiedBanner({
  modified,
  onReset,
}: {
  modified: ModifyResponse;
  onReset: () => void;
}) {
  const {
    operation,
    note,
    swap,
    added_allergens,
    removed_allergens,
    knock_on_flags,
    warnings,
  } = modified;
  const hasAllergenChange =
    removed_allergens.length > 0 || added_allergens.length > 0;

  const isRemove = operation === "remove";
  const substituted = isRemove && swap.to_ingredient !== "(removed)";
  const headline = !isRemove ? (
    <>
      Modified:{" "}
      <span className="font-medium text-primary">{swap.to_ingredient}</span> for{" "}
      {swap.from_ingredient} ({swap.ratio})
    </>
  ) : substituted ? (
    <>
      Used <span className="font-medium text-primary">{swap.to_ingredient}</span>{" "}
      instead of {swap.from_ingredient}
    </>
  ) : (
    <>
      Removed{" "}
      <span className="font-medium text-primary">{swap.from_ingredient}</span>
    </>
  );

  return (
    <div className="space-y-3 rounded-xl border border-primary/30 bg-primary/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm">{headline}</p>
          {note && <p className="text-sm text-muted-foreground">{note}</p>}
          {hasAllergenChange && (
            <p className="text-sm font-medium">
              This swap{" "}
              {removed_allergens.length > 0 && (
                <span className="text-primary">
                  removes {removed_allergens.join(", ")}
                </span>
              )}
              {removed_allergens.length > 0 && added_allergens.length > 0 && " · "}
              {added_allergens.length > 0 && (
                <span className="text-destructive">
                  adds {added_allergens.join(", ")}
                </span>
              )}
              .
            </p>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={onReset}>
          <RotateCcw className="mr-1 size-3.5" /> Reset
        </Button>
      </div>

      {knock_on_flags.length > 0 && (
        <ul className="space-y-1 border-t border-primary/15 pt-3">
          {knock_on_flags.map((flag, i) => (
            <li key={i} className="flex gap-2 text-xs text-muted-foreground">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-primary/70" />
              <span>{flag}</span>
            </li>
          ))}
        </ul>
      )}

      {warnings.map((w, i) => (
        <p key={i} className="flex gap-2 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" />
          <span>{w}</span>
        </p>
      ))}
    </div>
  );
}
