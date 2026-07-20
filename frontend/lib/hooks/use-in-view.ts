"use client";

import { useLayoutEffect, useRef, useState } from "react";

// SSR-safe layout effect (no-op on the server).
const useIso = typeof window !== "undefined" ? useLayoutEffect : () => {};

export type RevealState = "idle" | "hidden" | "shown";

// Drives a one-shot scroll reveal without a flash:
//  - SSR / pre-mount → "idle" (rendered fully visible; content never needs JS)
//  - above-the-fold on first paint → "shown" immediately (fades in on load)
//  - below-the-fold → "hidden" (off-screen, no visible flash) then "shown" on scroll
export function useInView<T extends Element = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [state, setState] = useState<RevealState>("idle");

  useIso(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setState("shown");
      return;
    }
    // Already in the viewport at first paint → reveal now, no hidden frame.
    if (el.getBoundingClientRect().top < window.innerHeight * 0.95) {
      setState("shown");
      return;
    }
    setState("hidden");
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setState("shown");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return { ref, state };
}
