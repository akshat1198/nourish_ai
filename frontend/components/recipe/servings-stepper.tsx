"use client";

import { Minus, Plus, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";

const MIN = 1;
const MAX = 12;

function factorLabel(value: number, base: number): string {
  const f = base > 0 ? value / base : 1;
  return `×${Math.round(f * 100) / 100}`;
}

export function ServingsStepper({
  value,
  base,
  onChange,
}: {
  value: number;
  base: number;
  onChange: (next: number) => void;
}) {
  const stepBtn =
    "grid size-8 place-items-center text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-40";

  return (
    <div className="flex items-center gap-3">
      <div className="inline-flex items-center rounded-full border border-border bg-card">
        <button
          type="button"
          aria-label="Fewer servings"
          disabled={value <= MIN}
          onClick={() => onChange(value - 1)}
          className={cn(stepBtn, "rounded-l-full")}
        >
          <Minus className="size-3.5" />
        </button>
        <span
          className="tabular min-w-[5.5rem] px-1 text-center text-sm font-medium"
          aria-live="polite"
        >
          Serves {value}
        </span>
        <button
          type="button"
          aria-label="More servings"
          disabled={value >= MAX}
          onClick={() => onChange(value + 1)}
          className={cn(stepBtn, "rounded-r-full")}
        >
          <Plus className="size-3.5" />
        </button>
      </div>

      {value !== base && (
        <button
          type="button"
          onClick={() => onChange(base)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RotateCcw className="size-3" />
          <span className="tabular">{factorLabel(value, base)}</span> · reset
        </button>
      )}
    </div>
  );
}
