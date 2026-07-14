import { DOT_COLOR, type IngredientCategory } from "@/components/ingredient-token";

// Map backend ingredient categories -> the token's dot palette.
const MAP: Record<string, IngredientCategory> = {
  vegetable: "veg",
  protein: "protein",
  grain: "grain",
  dairy: "dairy",
  spice: "spice",
  herb: "spice",
  fruit: "fruit",
  starch: "grain",
  pantry: "other",
  sauce: "other",
};

export function toDotCategory(category?: string | null): IngredientCategory {
  return (category && MAP[category]) || "other";
}

// Tailwind class for the category dot, straight from a backend category string.
export function dotClass(category?: string | null): string {
  return DOT_COLOR[toDotCategory(category)];
}
