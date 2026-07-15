"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Globe, Search } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useWebSearch } from "@/lib/hooks/use-web-search";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

// Discovery only: results link out to the original recipe and never enter the
// pantry-matched corpus. Dormant (shows a hint) until Edamam creds are set.
export function WebSearchPanel() {
  const [q, setQ] = useState("");
  const debounced = useDebounced(q.trim(), 350);
  const { data, isFetching } = useWebSearch(debounced);

  return (
    <section className="space-y-3">
      <div>
        <h2 className="flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Globe className="size-5 text-primary" />
          Search the wider web
        </h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Look beyond your pantry — results link out to the original recipe.
        </p>
      </div>

      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search any recipe on the web…"
          aria-label="Search the web for recipes"
          autoComplete="off"
          spellCheck={false}
          className="h-11 w-full rounded-lg border border-input bg-card pl-10 pr-4 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>

      {debounced.length >= 2 && data && !data.enabled && (
        <Card className="border-dashed bg-transparent p-5 text-center text-sm text-muted-foreground">
          Web search isn&apos;t set up yet. Add Edamam API keys to enable it —
          your pantry recommendations work without it.
        </Card>
      )}

      {isFetching && (
        <div className="grid gap-3 sm:grid-cols-2">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      )}

      {data?.enabled && !isFetching && data.results.length === 0 && debounced.length >= 2 && (
        <p className="text-sm text-muted-foreground">No web results for that search.</p>
      )}

      {data?.enabled && data.results.length > 0 && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.results.map((r) => (
              <a
                key={r.url}
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-[transform,box-shadow] hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {r.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={r.image_url}
                    alt=""
                    width={56}
                    height={56}
                    className="size-14 shrink-0 rounded-lg object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="grid size-14 shrink-0 place-items-center rounded-lg bg-secondary">
                    <Globe className="size-5 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium group-hover:text-primary">{r.title}</p>
                  {r.source && (
                    <p className="truncate text-xs text-muted-foreground">{r.source}</p>
                  )}
                </div>
                <ExternalLink className="size-4 shrink-0 text-muted-foreground" />
              </a>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{data.attribution}</p>
        </>
      )}
    </section>
  );
}
