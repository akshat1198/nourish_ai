import type { FilterAnswers } from "@/lib/filter-options";
import { getSessionId } from "@/lib/track";
import type { PantryItem, RecommendRequest } from "@/types/api";

// Compose the questionnaire answers + the current pantry into a RecommendRequest.
// Extracted verbatim from the old FilterFlow.submit so the paged results page
// builds exactly the same request the single-page flow did.
export function buildRequest(
  answers: FilterAnswers,
  pantry: PantryItem[],
): RecommendRequest {
  return {
    pantry: pantry.map((i) => i.ingredient),
    exclude_allergens: answers.exclude_allergens,
    disliked_ingredients: answers.disliked_ingredients,
    cuisines: answers.cuisines,
    meal_type: answers.meal_type,
    nutrition_goals: answers.nutrition_goals,
    diet: answers.diet,
    max_time_minutes: answers.max_time_minutes,
    limit: 15, // surface a comfortable set (≥10 when the corpus allows)
    session_id: getSessionId(), // Stage 13: A/B bucketing
  };
}
