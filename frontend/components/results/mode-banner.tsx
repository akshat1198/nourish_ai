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

  const substitution = mode === "substitution_first";
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm",
        substitution
          ? "border-turmeric/40 bg-turmeric/10"
          : "border-primary/30 bg-primary/8",
      )}
    >
      <Info
        className={cn(
          "mt-0.5 size-4 shrink-0",
          substitution ? "text-turmeric" : "text-primary",
        )}
      />
      <div>
        <p className="font-medium text-foreground">
          {substitution
            ? "Not much matched — but these work with a swap"
            : "Best options — you'll need a few extra items"}
        </p>
        {explanation && (
          <p className="mt-0.5 text-muted-foreground">{explanation}</p>
        )}
      </div>
    </div>
  );
}
