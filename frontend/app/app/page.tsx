"use client";

import { ArrowRight } from "lucide-react";
import { PantryManager } from "@/components/pantry/pantry-manager";
import { Button } from "@/components/ui/button";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";

// Step 1 of the flow: get the pantry current, then head into the filters.
// Header, aurora, and the shared provider live in app/app/layout.tsx.
export default function PantryPage() {
  const { startFlow } = useFilterFlow();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-5xl font-semibold tracking-tight">
          Your kitchen
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Keep your pantry current — then tell us what you&apos;re in the mood
          for.
        </p>
      </div>

      <PantryManager />

      <div className="flex justify-end">
        <Button
          size="lg"
          className="glow-primary gap-2"
          onClick={startFlow}
        >
          Start cooking <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
