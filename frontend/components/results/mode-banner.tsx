import { Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RecommendMode } from "@/types/api";

export function ModeBanner({
  mode,
  explanation,
}: {
  mode: RecommendMode;
  explanation: string | null;
}) {
  if (mode === "normal") return null;

  // Warm (turmeric) for "you'll need to do something" modes; primary otherwise.
  const warm = mode === "substitution_first" || mode === "off_cuisine";
  const title =
    mode === "substitution_first"
      ? "Not much matched — but these work with a swap"
      : mode === "off_cuisine"
        ? "We're short on recipes in that cuisine"
        : "Best options — you'll need a few extra items";
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm",
        warm ? "border-turmeric/40 bg-turmeric/10" : "border-primary/30 bg-primary/8",
      )}
    >
      <Info
        aria-hidden="true"
        className={cn("mt-0.5 size-4 shrink-0", warm ? "text-turmeric" : "text-primary")}
      />
      <div>
        <p className="font-medium text-foreground">{title}</p>
        {explanation && (
          <p className="mt-0.5 text-muted-foreground">{explanation}</p>
        )}
      </div>
    </div>
  );
}
