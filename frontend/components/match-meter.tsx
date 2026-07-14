import { cn } from "@/lib/utils";

// Pantry-match as filled/hollow dots — the recipe-card counterpart to the
// ingredient token (not a generic progress bar).
export function MatchMeter({ have, total }: { have: number; total: number }) {
  return (
    <span
      className="inline-flex items-center gap-1"
      aria-label={`${have} of ${total} key ingredients on hand`}
    >
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
