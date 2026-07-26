import { ExternalLink, Sparkles } from "lucide-react";
import type { RecipeDetail } from "@/types/api";

// Imported recipes (themealdb / archanas) link back to the original per source
// TOS; seed recipes are ours and render nothing.
export function AttributionFooter({ recipe }: { recipe: RecipeDetail }) {
  // A written recipe has no source to link, but staying silent would let it
  // pass as one someone has actually cooked. Say where it came from.
  if (recipe.source === "generated") {
    return (
      <footer className="flex items-start gap-2.5 border-t border-border pt-6 text-sm text-muted-foreground">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-turmeric" aria-hidden="true" />
        <p>
          Written for your filters because nothing in the collection fit. It
          hasn&apos;t been kitchen-tested — treat the quantities and timings as a
          starting point.
        </p>
      </footer>
    );
  }

  if (!recipe.source_url) return null;

  return (
    <footer className="space-y-1 border-t border-border pt-6 text-sm text-muted-foreground">
      <a
        href={recipe.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-primary hover:underline"
      >
        View the original recipe
        <ExternalLink className="size-3.5" />
      </a>
      {recipe.attribution && <p>Recipe courtesy of {recipe.attribution}.</p>}
      {recipe.license_note && (
        <p className="text-xs text-muted-foreground/80">{recipe.license_note}</p>
      )}
    </footer>
  );
}
