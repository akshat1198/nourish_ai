import { ChefHat, Refrigerator, SlidersHorizontal } from "lucide-react";
import { LandingHero } from "@/components/landing/landing-hero";
import { Reveal } from "@/components/reveal";
import { Card } from "@/components/ui/card";

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

// The landing is an art-directed dark experience (forced `.dark`); the /app tool
// keeps its own light/dark toggle.
export default function Home() {
  return (
    <div className="dark min-h-dvh bg-background text-foreground">
      <LandingHero />

      {/* How it works — dark, numbered, editorial */}
      <section id="how" className="relative overflow-hidden border-t border-border/60">
        {/* faint aurora continuity behind the section */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-24 left-1/4 -z-0 size-[32rem] rounded-full bg-primary/10 blur-[130px]"
        />
        <div className="relative mx-auto w-full max-w-6xl px-6 py-24">
          <Reveal>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-primary">
              How it works
            </p>
            <h2 className="mt-3 font-display text-4xl font-medium tracking-tight sm:text-5xl">
              Dinner, sorted in three steps
            </h2>
            <p className="mt-3 max-w-lg text-muted-foreground">
              From a full pantry to a plan you&apos;ll actually cook.
            </p>
          </Reveal>

          <div className="mt-14 grid gap-6 sm:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <Reveal key={title} delay={i * 90}>
                <Card className="group h-full border-border/60 bg-card/60 p-7 backdrop-blur transition-[transform,box-shadow] duration-300 hover:-translate-y-1.5 hover:shadow-2xl hover:shadow-black/30">
                  <span className="font-display text-5xl font-light text-primary/30">
                    0{i + 1}
                  </span>
                  <div className="mt-5 grid size-11 place-items-center rounded-xl bg-primary/15 text-primary">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-5 font-display text-2xl font-medium">{title}</h3>
                  <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                    {body}
                  </p>
                </Card>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/60">
        <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-3 gap-y-2 px-6 py-8 text-sm text-muted-foreground">
          <span className="font-display text-lg font-semibold text-foreground">
            Nourish<span className="text-primary">AI</span>
          </span>
          <span className="ml-auto text-xs">Cook what you already have.</span>
        </div>
      </footer>
    </div>
  );
}
