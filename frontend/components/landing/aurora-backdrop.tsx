"use client";

import { useEffect, useRef } from "react";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";

// Fine tiled turbulence for a paper-and-pigment grain. Very low opacity.
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

// The signature: a living "spice-bloom" aurora — herb-green + honey pigments
// diffusing like warm light, with a subtle pointer parallax and a film grain.
// Drift + parallax are both disabled under reduced motion; parallax is fine-
// pointer only (no-op on touch).
export function AuroraBackdrop() {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const raf = useRef(0);

  useEffect(() => {
    if (reduced) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const el = ref.current;
    if (!el) return;

    const onMove = (e: MouseEvent) => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const x = (e.clientX / window.innerWidth - 0.5) * 2; // -1..1
        const y = (e.clientY / window.innerHeight - 0.5) * 2;
        el.style.setProperty("--aurora-x", `${x * 18}px`);
        el.style.setProperty("--aurora-y", `${y * 18}px`);
      });
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf.current);
    };
  }, [reduced]);

  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      style={{ "--aurora-x": "0px", "--aurora-y": "0px" } as React.CSSProperties}
    >
      {/* soft base tint for depth */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 90% at 50% -10%, color-mix(in oklab, var(--primary) 10%, transparent), transparent 60%)",
        }}
      />
      {/* parallax layer holding the pigment blobs */}
      <div
        className="absolute inset-0 will-change-transform"
        style={{ transform: "translate3d(var(--aurora-x), var(--aurora-y), 0)" }}
      >
        <div className="animate-aurora absolute -left-40 -top-32 size-[44rem] rounded-full bg-primary/30 blur-3xl" />
        <div className="animate-aurora absolute -right-48 top-1/4 size-[40rem] rounded-full bg-turmeric/25 blur-3xl [animation-delay:-6s]" />
        <div className="animate-aurora absolute -bottom-44 left-1/4 size-[38rem] rounded-full bg-primary/20 blur-3xl [animation-delay:-11s]" />
        <div className="animate-aurora absolute -top-24 right-1/4 size-[26rem] rounded-full bg-turmeric/20 blur-3xl [animation-delay:-3s]" />
      </div>
      {/* film grain */}
      <div
        className="absolute inset-0 opacity-[0.06] mix-blend-soft-light"
        style={{ backgroundImage: GRAIN }}
      />
    </div>
  );
}
