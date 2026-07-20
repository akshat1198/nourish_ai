import { ExternalLink } from "lucide-react";
import type { RecipeDetail } from "@/types/api";

// Imported recipes (themealdb / archanas) link back to the original per source
// TOS; seed recipes are ours and render nothing.
export function AttributionFooter({ recipe }: { recipe: RecipeDetail }) {
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
