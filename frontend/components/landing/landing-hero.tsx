"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { IngredientToken } from "@/components/ingredient-token";
import { KitchenStatus } from "@/components/kitchen-status";
import { Magnetic } from "@/components/magnetic";
import { UserMenu } from "@/components/user-menu";
import { buttonVariants } from "@/components/ui/button";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='120'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")";

// Ambient "your pantry, alive" constellation framing the headline.
const FLOATERS = [
  { name: "tomato", category: "veg", pos: "left-[6%] top-[26%]", delay: "0s" },
  { name: "basil", category: "spice", pos: "right-[9%] top-[22%]", delay: "-2.4s" },
  { name: "chickpeas", category: "protein", pos: "left-[11%] top-[60%]", delay: "-1.1s" },
  { name: "lemon", category: "fruit", pos: "right-[7%] top-[56%]", delay: "-3.6s" },
  { name: "garlic", category: "veg", pos: "left-[22%] bottom-[14%]", delay: "-4.8s" },
  { name: "paneer", category: "dairy", pos: "right-[20%] bottom-[17%]", delay: "-1.9s" },
] as const;

export function LandingHero() {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const raf = useRef(0);

  useEffect(() => {
    if (reduced) return;
    if (!window.matchMedia("(pointer: fine)").matches) return;
    const el = ref.current;
    if (!el) return;
    const onMove = (e: MouseEvent) => {
      cancelAnimationFrame(raf.current);
      raf.current = requestAnimationFrame(() => {
        const x = e.clientX / window.innerWidth - 0.5;
        const y = e.clientY / window.innerHeight - 0.5;
        el.style.setProperty("--px", `${x * 40}px`);
        el.style.setProperty("--py", `${y * 40}px`);
      });
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf.current);
    };
  }, [reduced]);

  return (
    <section
      ref={ref}
      className="relative flex min-h-dvh flex-col overflow-hidden"
      style={{ "--px": "0px", "--py": "0px" } as React.CSSProperties}
    >
      {/* cranked, clearly-moving aurora (parallax: strong) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 will-change-transform"
        style={{ transform: "translate3d(var(--px), var(--py), 0)" }}
      >
        <div className="animate-aurora absolute -left-32 top-[-10%] size-[52rem] rounded-full bg-primary/40 blur-[130px]" />
        <div className="animate-aurora absolute right-[-12%] top-[18%] size-[46rem] rounded-full bg-turmeric/40 blur-[130px] [animation-delay:-6s]" />
        <div className="animate-aurora absolute bottom-[-18%] left-1/3 size-[42rem] rounded-full bg-[var(--chili)] opacity-25 blur-[130px] [animation-delay:-11s]" />
        <div className="animate-aurora absolute left-1/2 top-1/3 size-[32rem] -translate-x-1/2 rounded-full bg-turmeric/25 blur-[110px] [animation-delay:-3s]" />
      </div>

      {/* film grain */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.07] mix-blend-soft-light"
        style={{ backgroundImage: GRAIN }}
      />

      {/* floating pantry tokens (parallax: gentle, opposite depth) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 hidden will-change-transform md:block"
        style={{ transform: "translate3d(calc(var(--px) * -0.5), calc(var(--py) * -0.5), 0)" }}
      >
        {FLOATERS.map((f) => (
          <div
            key={f.name}
            className={cn("animate-float absolute opacity-70", f.pos)}
            style={{ animationDelay: f.delay } as React.CSSProperties}
          >
            <IngredientToken name={f.name} category={f.category} />
          </div>
        ))}
      </div>

      {/* header */}
      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <span className="font-display text-2xl font-semibold tracking-tight">
          Nourish<span className="text-primary">AI</span>
        </span>
        <div className="flex items-center gap-3">
          <KitchenStatus />
          <UserMenu />
        </div>
      </header>

      {/* content */}
      <div className="relative z-10 mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center px-6 pb-24 text-center">
        <p className="animate-fade-up mb-7 inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/10 px-3.5 py-1.5 text-xs font-medium text-primary">
          <Sparkles className="size-3.5" />
          AI recipes from what&apos;s already in your kitchen
        </p>

        <h1
          className="animate-fade-up font-display text-6xl font-medium leading-[0.92] tracking-tight text-balance sm:text-7xl md:text-[7.5rem]"
          style={{ animationDelay: "80ms" }}
        >
          Cook what you
          <br />
          <span className="text-simmer italic">already have.</span>
        </h1>

        <p
          className="animate-fade-up mt-8 max-w-xl text-lg leading-relaxed text-muted-foreground"
          style={{ animationDelay: "200ms" }}
        >
          Tell us your pantry and tonight&apos;s mood. Get recipes across every
          cuisine you can actually make right now — no last-minute grocery run.
        </p>

        <div
          className="animate-fade-up mt-11 flex flex-col items-center gap-4"
          style={{ animationDelay: "320ms" }}
        >
          <Magnetic strength={0.4}>
            <Link
              href="/app"
              className={cn(
                buttonVariants({ size: "lg" }),
                "group h-14 px-9 text-base glow-primary",
              )}
            >
              Set up my pantry
              <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
            </Link>
          </Magnetic>
          <span className="text-sm text-muted-foreground">
            Free · your pantry, your recipes
          </span>
        </div>
      </div>
    </section>
  );
}
