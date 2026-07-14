import { EMPTY_ANSWERS, type FilterAnswers } from "@/lib/filter-options";

const KEY = "nourish:last-filters:v1";

export function loadLastFilters(): FilterAnswers | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    return { ...EMPTY_ANSWERS, ...(JSON.parse(raw) as Partial<FilterAnswers>) };
  } catch {
    return null;
  }
}

export function saveLastFilters(answers: FilterAnswers): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(answers));
  } catch {
    /* storage full / unavailable — non-fatal */
  }
}
