"use client";

import { useState } from "react";
import { ArrowLeftRight } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useSubstitutions } from "@/lib/hooks/use-substitutions";
import { titleCase } from "@/lib/filter-options";

export function SwapPopover({
  ingredient,
  onApply,
  pending,
}: {
  ingredient: string;
  onApply: (to: string) => void;
  pending: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useSubstitutions(ingredient, open);
  const subs = data?.substitutes ?? [];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Swap ${ingredient}`}
          className="relative grid size-6 touch-manipulation place-items-center rounded-full text-muted-foreground transition-colors before:absolute before:left-1/2 before:top-1/2 before:size-11 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeftRight className="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(16rem,calc(100vw-2rem))] p-3">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Swap {ingredient} for
        </p>
        {isLoading && (
          <p className="text-sm text-muted-foreground">Finding swaps…</p>
        )}
        {!isLoading && subs.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No known swaps for this ingredient.
          </p>
        )}
        <ul className="space-y-0.5">
          {subs.map((s) => (
            <li key={s.use}>
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  onApply(s.use);
                  setOpen(false);
                }}
                className="flex w-full flex-col rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                <span className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">{s.use}</span>
                  <span className="tabular text-xs text-muted-foreground">
                    {s.ratio}
                  </span>
                </span>
                {s.enables_diets.length > 0 && (
                  <span className="text-xs text-primary">
                    enables {s.enables_diets.map((d) => titleCase(d.replace(/_/g, " "))).join(", ")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
