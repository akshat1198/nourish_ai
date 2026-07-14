"use client";

import { useEffect, useState } from "react";
import { Clock3 } from "lucide-react";
import {
  IngredientToken,
  type IngredientCategory,
} from "@/components/ingredient-token";
import { MatchMeter } from "@/components/match-meter";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useReducedMotion } from "@/lib/hooks/use-reduced-motion";
import { cn } from "@/lib/utils";

interface Demo {
  cuisine: string;
  title: string;
  time: number;
  protein: number;
  have: number;
  total: number;
  tokens: { name: string; cat: IngredientCategory }[];
}

// Deliberately global — a spread of cuisines, not one theme.
const DEMOS: Demo[] = [
  {
    cuisine: "Italian",
    title: "Garlic Basil Pasta",
    time: 20,
    protein: 16,
    have: 4,
    total: 5,
    tokens: [
      { name: "pasta", cat: "grain" },
      { name: "tomato", cat: "veg" },
      { name: "garlic", cat: "veg" },
      { name: "basil", cat: "spice" },
      { name: "parmesan", cat: "dairy" },
    ],
  },
  {
    cuisine: "Mexican",
    title: "Chicken Street Tacos",
    time: 25,
    protein: 32,
    have: 3,
    total: 5,
    tokens: [
      { name: "chicken", cat: "protein" },
      { name: "tortillas", cat: "grain" },
      { name: "lime", cat: "fruit" },
      { name: "cilantro", cat: "spice" },
      { name: "onion", cat: "veg" },
    ],
  },
  {
    cuisine: "Thai",
    title: "Ginger Tofu Stir-Fry",
    time: 18,
    protein: 22,
    have: 5,
    total: 5,
    tokens: [
      { name: "tofu", cat: "protein" },
      { name: "broccoli", cat: "veg" },
      { name: "ginger", cat: "spice" },
      { name: "soy sauce", cat: "other" },
      { name: "rice", cat: "grain" },
    ],
  },
  {
    cuisine: "Mediterranean",
    title: "Chickpea Feta Bowl",
    time: 15,
    protein: 18,
    have: 4,
    total: 6,
    tokens: [
      { name: "chickpeas", cat: "protein" },
      { name: "cucumber", cat: "veg" },
      { name: "feta", cat: "dairy" },
      { name: "lemon", cat: "fruit" },
      { name: "olive oil", cat: "other" },
    ],
  },
];

export function HeroShowcase() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced || paused) return;
    const id = setInterval(
      () => setActive((n) => (n + 1) % DEMOS.length),
      3800,
    );
    return () => clearInterval(id);
  }, [reduced, paused]);

  const d = DEMOS[active];

  return (
    <div
      className="relative w-full max-w-md"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* soft depth behind the card */}
      <div className="pointer-events-none absolute -inset-8 -z-10 rounded-[2.5rem] bg-primary/8 blur-3xl" />

      <Card className="glow-warm overflow-hidden p-0 animate-float">
        <div className="flex items-center justify-between border-b border-border/70 bg-secondary/40 px-5 py-3">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            What you have
          </span>
          <span className="text-xs text-muted-foreground">tonight</span>
        </div>

        <div key={active} className="p-6">
          <div className="flex flex-wrap gap-2">
            {d.tokens.map((t, idx) => (
              <span
                key={t.name}
                className={cn(!reduced && "animate-pop-in")}
                style={reduced ? undefined : { animationDelay: `${idx * 70}ms` }}
              >
                <IngredientToken name={t.name} category={t.cat} />
              </span>
            ))}
          </div>

          <div className="my-5 flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              becomes
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <div
            className={cn(
              "flex items-start justify-between gap-3",
              !reduced && "animate-fade-up",
            )}
          >
            <div>
              <h3 className="font-display text-2xl font-semibold leading-tight">
                {d.title}
              </h3>
              <div className="mt-2 flex items-center gap-3 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1 tabular">
                  <Clock3 className="size-3.5" /> {d.time} min
                </span>
                <span className="tabular">{d.protein}g protein</span>
              </div>
            </div>
            <Badge variant="primary">{d.cuisine}</Badge>
          </div>

          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <MatchMeter have={d.have} total={d.total} />
            <span className="tabular">
              {d.have} of {d.total} on hand
            </span>
          </div>
        </div>
      </Card>

      <div className="mt-4 flex justify-center gap-2">
        {DEMOS.map((demo, idx) => (
          <button
            key={demo.cuisine}
            onClick={() => setActive(idx)}
            aria-label={`Show ${demo.cuisine} example`}
            className={cn(
              "h-1.5 rounded-full transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              idx === active
                ? "w-6 bg-primary"
                : "w-1.5 bg-cardamom hover:bg-muted-foreground",
            )}
          />
        ))}
      </div>
    </div>
  );
}
