"use client";

import { useInView } from "@/lib/hooks/use-in-view";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

// Subtle scroll-reveal wrapper: fades + rises its children in when they enter
// the viewport (once). Reduced motion → renders plain and visible.
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const { ref, state } = useInView<HTMLDivElement>();

  if (reduced) return <div className={className}>{children}</div>;

  return (
    <div
      ref={ref}
      className={cn(
        className,
        state === "hidden" && "opacity-0",
        state === "shown" && "animate-fade-up",
      )}
      style={state === "shown" && delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}
