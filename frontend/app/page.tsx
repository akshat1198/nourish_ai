"use client";

import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ChefHat,
  Refrigerator,
  Sparkles,
  SlidersHorizontal,
} from "lucide-react";
import { AuroraBackdrop } from "@/components/landing/aurora-backdrop";
import { HeroShowcase } from "@/components/landing/hero-showcase";
import { KitchenStatus } from "@/components/kitchen-status";
import { Magnetic } from "@/components/magnetic";
import { Reveal } from "@/components/reveal";
import { UserMenu } from "@/components/user-menu";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    icon: Refrigerator,
    title: "Stock your pantry",
    body: "Add what's on hand plus your everyday staples. It stays saved and you edit it whenever.",
  },
  {
    icon: SlidersHorizontal,
    title: "Set tonight's mood",
    body: "Cuisine, meal, how you want to eat, and anything to skip — a few quick taps.",
  },
  {
    icon: ChefHat,
    title: "Cook something great",
    body: "Ranked recipes you can actually make right now, with smart swaps when you're short.",
  },
];

export default function Home() {
  const router = useRouter();
  return (
    <div className="flex min-h-dvh flex-col">
      {/* Header */}
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-5">
        <span className="font-display text-2xl font-semibold tracking-tight">
          Nourish<span className="text-primary">AI</span>
        </span>
        <div className="flex items-center gap-4">
          <KitchenStatus />
          <UserMenu />
        </div>
      </header>

      <main className="flex flex-1 flex-col">
      {/* Hero */}
      <section className="relative flex-1 overflow-hidden">
        <AuroraBackdrop />

        <div className="mx-auto grid w-full max-w-6xl items-center gap-14 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-24">
          {/* Left — the pitch */}
          <div className={cn("animate-fade-up")}>
            <p className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="size-3.5" />
              AI recipes from what’s already in your kitchen
            </p>

            <h1 className="font-display text-6xl font-semibold leading-[0.98] tracking-tight text-balance sm:text-7xl">
              Cook what you{" "}
              <span className="text-primary">already have.</span>
            </h1>

            <p className="mt-6 max-w-md text-lg leading-relaxed text-muted-foreground">
              Keep your pantry current, tell us the mood, and get recipes across
              every cuisine that you can actually make tonight — no last-minute
              grocery run.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-4">
              <Magnetic>
                <Button
                  size="lg"
                  className="group glow-primary"
                  onClick={() => router.push("/app")}
                >
                  Set up my pantry
                  <ArrowRight className="transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Magnetic>
              <span className="text-sm text-muted-foreground">
                Free · your pantry, your recipes
              </span>
            </div>
          </div>

          {/* Right — the living demo */}
          <div className="flex justify-center lg:justify-end">
            <HeroShowcase />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="border-t border-border bg-card/40">
        <div className="mx-auto w-full max-w-6xl px-6 py-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight">
            Dinner, sorted in three steps
          </h2>
          <p className="mt-2 max-w-lg text-muted-foreground">
            From a full pantry to a plan you’ll actually cook.
          </p>

          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <Reveal key={title} delay={i * 90}>
                <Card className="h-full p-6 transition-[transform,box-shadow] duration-200 hover:-translate-y-1 hover:shadow-md">
                  <div className="grid size-11 place-items-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-4 font-display text-xl font-medium">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {body}
                  </p>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-2 gap-y-1 px-6 py-6 text-sm text-muted-foreground">
          <span className="font-display text-base font-semibold text-foreground">
            Nourish<span className="text-primary">AI</span>
          </span>
          <span className="ml-auto text-xs">Foundation · Stage 5.2</span>
        </div>
      </footer>
    </div>
  );
}
