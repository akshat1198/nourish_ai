"use client";

import { useState } from "react";
import { ArrowLeftRight, ArrowRight } from "lucide-react";
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
  const [custom, setCustom] = useState("");
  const { data, isLoading } = useSubstitutions(ingredient, open);
  const subs = data?.substitutes ?? [];

  const apply = (to: string) => {
    const name = to.trim();
    if (!name) return;
    onApply(name);
    setOpen(false);
    setCustom("");
  };

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
      <PopoverContent className="w-[min(20rem,calc(100vw-2rem))] p-3">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Swap {ingredient} for
        </p>
        {isLoading && (
          <p className="py-1 text-sm text-muted-foreground">Finding swaps…</p>
        )}
        {!isLoading && subs.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No suggestions — try typing one below.
          </p>
        )}
        <ul className="space-y-0.5">
          {subs.map((s) => (
            <li key={s.use}>
              <button
                type="button"
                disabled={pending}
                onClick={() => apply(s.use)}
                className="flex w-full flex-col rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
              >
                <span className="flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">{s.use}</span>
                  <span className="tabular text-xs text-muted-foreground">
                    {s.ratio}
                  </span>
                </span>
                {s.note && (
                  <span className="text-xs text-muted-foreground">{s.note}</span>
                )}
                {s.enables_diets.length > 0 && (
                  <span className="text-xs text-primary">
                    enables {s.enables_diets.map((d) => titleCase(d.replace(/_/g, " "))).join(", ")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>

        {/* Free-text: swap in anything, even outside our vocabulary. */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            apply(custom);
          }}
          className="mt-2 flex items-center gap-1.5 border-t border-border pt-2"
        >
          <input
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            placeholder="type another…"
            aria-label={`Swap ${ingredient} for something else`}
            className="min-w-0 flex-1 rounded-md border border-border bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="submit"
            disabled={pending || !custom.trim()}
            aria-label="Apply this swap"
            className="grid size-7 shrink-0 touch-manipulation place-items-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"
          >
            <ArrowRight className="size-4" />
          </button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
