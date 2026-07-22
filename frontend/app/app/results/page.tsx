"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ResultsList } from "@/components/results/results-list";
import { buildRequest } from "@/lib/flow/build-request";
import { useFilterFlow } from "@/lib/flow/filter-flow-context";
import { usePantry } from "@/lib/hooks/use-pantry";

export default function ResultsPage() {
  const { answers, ready } = useFilterFlow();
  const pantry = usePantry();

  // Build the same RecommendRequest the old single-page flow did — once answers
  // are hydrated. ResultsList owns the actual query.
  const request = useMemo(
    () => (ready ? buildRequest(answers, pantry.data?.items ?? []) : null),
    [ready, answers, pantry.data],
  );

  return (
    <div className="space-y-6">
      <Link
        href="/app/filters/review"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Refine filters
      </Link>
      <ResultsList request={request} />
    </div>
  );
}
