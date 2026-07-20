import { Pin, X } from "lucide-react";
import { cn } from "@/lib/utils";

// The signature element: a tactile ingredient pill with a masala-dabba category
// dot. Used identically for pantry items, staples, dislikes, and a recipe's
// missing ingredients — the one visual motif that ties the whole app together.

export type IngredientCategory =
  | "protein"
  | "veg"
  | "grain"
  | "spice"
  | "dairy"
  | "fruit"
  | "other";

export const DOT_COLOR: Record<IngredientCategory, string> = {
  protein: "bg-cat-protein",
  veg: "bg-cat-veg",
  grain: "bg-cat-grain",
  spice: "bg-cat-spice",
  dairy: "bg-cat-dairy",
  fruit: "bg-cat-fruit",
  other: "bg-cat-other",
};

interface IngredientTokenProps {
  name: string;
  category?: IngredientCategory;
  /** Staples read as "always on hand": a pressed, pinned treatment. */
  staple?: boolean;
  /** Missing ingredients (on a recipe) read as an outline you don't have yet. */
  muted?: boolean;
  /** When provided, shows a pin toggle that flips staple state. */
  onToggleStaple?: () => void;
  onRemove?: () => void;
}

export function IngredientToken({
  name,
  category = "other",
  staple = false,
  muted = false,
  onToggleStaple,
  onRemove,
}: IngredientTokenProps) {
  return (
    <span
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-sm transition-colors",
        staple
          ? "border-primary/25 bg-primary/8 text-foreground"
          : "border-border bg-card text-foreground",
        muted && "border-dashed bg-transparent text-muted-foreground",
      )}
    >
      <span className={cn("size-2 shrink-0 rounded-full", DOT_COLOR[category])} aria-hidden />
      <span className="leading-none">{name}</span>
      {onToggleStaple && (
        <button
          type="button"
          onClick={onToggleStaple}
          aria-label={staple ? `Unpin ${name} from staples` : `Pin ${name} as a staple`}
          aria-pressed={staple}
          className={cn(
            // visual stays size-5; a `before` pseudo widens the tap zone to
            // ~32px (mobile) with zero layout impact — see remove button below.
            "relative -mr-0.5 ml-0.5 grid size-5 touch-manipulation place-items-center rounded-full transition-colors before:absolute before:left-1/2 before:top-1/2 before:size-8 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            staple
              ? "text-primary hover:bg-primary/10"
              : "text-muted-foreground hover:bg-secondary hover:text-foreground",
          )}
        >
          <Pin className={cn("size-3", staple && "fill-current")} />
        </button>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${name}`}
          className="relative -mr-1 grid size-5 touch-manipulation place-items-center rounded-full text-muted-foreground before:absolute before:left-1/2 before:top-1/2 before:size-8 before:-translate-x-1/2 before:-translate-y-1/2 before:content-[''] hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  );
}
