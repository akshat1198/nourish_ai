"use client";

import { AnimatePresence, motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";

// Directional slide between the flow's pages, keyed on the pathname so each
// route change animates out/in. Direction comes from the store (which button
// was pressed); browser Back/Forward falls back to the last direction — a minor
// polish gap noted in the plan. Honors prefers-reduced-motion by rendering the
// child directly.
const EASE = [0.22, 1, 0.36, 1] as const;

export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { direction } = useFilterFlow();
  const reduced = useReducedMotion();

  if (reduced) return <>{children}</>;

  const dx = direction === "forward" ? 28 : -28;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, x: dx }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -dx }}
        transition={{ duration: 0.24, ease: EASE }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
