// Single source of truth for the paged filter flow. The order here drives the
// URL steps (`/app/filters/[step]`), the progress bar, and Back/Next resolution.
// `review` is the final step (the editable summary), so it counts toward the
// progress denominator just like it did in the old wizard.
export const STEP_SLUGS = [
  "cuisine",
  "meal",
  "diet",
  "avoid",
  "more",
  "review",
] as const;

export type StepSlug = (typeof STEP_SLUGS)[number];

// Question shown at the top of each step page.
export const STEP_TITLES: Record<StepSlug, string> = {
  cuisine: "What are you in the mood for?",
  meal: "Which meal?",
  diet: "How do you want to eat?",
  avoid: "Anything to avoid?",
  more: "Dislikes & time",
  review: "Ready to cook?",
};

export function isStepSlug(s: string | undefined): s is StepSlug {
  return s != null && (STEP_SLUGS as readonly string[]).includes(s);
}

export function stepIndex(slug: StepSlug): number {
  return STEP_SLUGS.indexOf(slug);
}

export function nextSlug(slug: StepSlug): StepSlug | null {
  const i = STEP_SLUGS.indexOf(slug);
  return i >= 0 && i < STEP_SLUGS.length - 1 ? STEP_SLUGS[i + 1] : null;
}

export function prevSlug(slug: StepSlug): StepSlug | null {
  const i = STEP_SLUGS.indexOf(slug);
  return i > 0 ? STEP_SLUGS[i - 1] : null;
}
