"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { usePathname, useRouter } from "next/navigation";
import { EMPTY_ANSWERS, type FilterAnswers } from "@/lib/filter-options";
import { loadLastFilters, saveLastFilters } from "@/lib/filters-storage";
import { isStepSlug, nextSlug, prevSlug, type StepSlug } from "@/lib/flow/steps";
import { useProfile } from "@/lib/hooks/use-profile";

// Direction of the last navigation — drives the slide direction in PageTransition.
type Direction = "forward" | "back";

interface FilterFlowValue {
  answers: FilterAnswers;
  setAnswers: Dispatch<SetStateAction<FilterAnswers>>;
  patch: (p: Partial<FilterAnswers>) => void;
  /** True once answers have been hydrated (profile defaults < last-used). */
  ready: boolean;
  direction: Direction;
  /** The current filter step, or null when not on a `/app/filters/[step]` route. */
  currentSlug: StepSlug | null;
  goNext: () => void;
  goBack: () => void;
  goToStep: (slug: StepSlug) => void;
  /** Pantry page → first filter. */
  startFlow: () => void;
  /** Review → results. */
  goToResults: () => void;
}

const Ctx = createContext<FilterFlowValue | null>(null);

export function useFilterFlow(): FilterFlowValue {
  const v = useContext(Ctx);
  if (!v)
    throw new Error("useFilterFlow must be used within <FilterFlowProvider>");
  return v;
}

// Lives in the shared `/app` layout, so it stays mounted across pantry → filter
// steps → results. That's what lets Back/Next preserve answers without a store
// library: the provider isn't remounted on navigation within the segment.
export function FilterFlowProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const profile = useProfile();

  const [answers, setAnswers] = useState<FilterAnswers>(EMPTY_ANSWERS);
  const [ready, setReady] = useState(false);
  const [direction, setDirection] = useState<Direction>("forward");

  // Hydrate once profile resolves — precedence: profile defaults < last-used.
  // Mirrors the old FilterFlow prefill; runs regardless of which page you land
  // on first, so deep-linking a step resumes with prior input.
  useEffect(() => {
    if (ready || profile.isLoading) return;
    const p = profile.data;
    const fromProfile: FilterAnswers = {
      ...EMPTY_ANSWERS,
      diet: p?.diet ?? null,
      exclude_allergens: p?.allergens ?? [],
      disliked_ingredients: p?.disliked_ingredients ?? [],
      cuisines: p?.cuisine_prefs ?? [],
    };
    const last = loadLastFilters();
    setAnswers(last ?? fromProfile);
    setReady(true);
  }, [ready, profile.isLoading, profile.data]);

  // Persist every change after hydration (same key the old flow used).
  useEffect(() => {
    if (ready) saveLastFilters(answers);
  }, [ready, answers]);

  const patch = useCallback(
    (p: Partial<FilterAnswers>) => setAnswers((a) => ({ ...a, ...p })),
    [],
  );

  const currentSlug = useMemo<StepSlug | null>(() => {
    const m = pathname.match(/^\/app\/filters\/([^/]+)/);
    return m && isStepSlug(m[1]) ? m[1] : null;
  }, [pathname]);

  const goToStep = useCallback(
    (slug: StepSlug) => {
      setDirection("forward");
      router.push(`/app/filters/${slug}`);
    },
    [router],
  );

  const startFlow = useCallback(() => {
    setDirection("forward");
    router.push("/app/filters/cuisine");
  }, [router]);

  const goToResults = useCallback(() => {
    setDirection("forward");
    router.push("/app/results");
  }, [router]);

  const goNext = useCallback(() => {
    if (!currentSlug) return;
    const n = nextSlug(currentSlug);
    setDirection("forward");
    if (n) router.push(`/app/filters/${n}`);
  }, [currentSlug, router]);

  const goBack = useCallback(() => {
    setDirection("back");
    // From the first step, Back returns to the pantry page.
    if (!currentSlug || currentSlug === "cuisine") {
      router.push("/app");
      return;
    }
    const p = prevSlug(currentSlug);
    if (p) router.push(`/app/filters/${p}`);
  }, [currentSlug, router]);

  const value = useMemo<FilterFlowValue>(
    () => ({
      answers,
      setAnswers,
      patch,
      ready,
      direction,
      currentSlug,
      goNext,
      goBack,
      goToStep,
      startFlow,
      goToResults,
    }),
    [
      answers,
      patch,
      ready,
      direction,
      currentSlug,
      goNext,
      goBack,
      goToStep,
      startFlow,
      goToResults,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
