"use client";

import { useEffect, useState } from "react";
import { Check, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useIngredientSearch } from "@/lib/hooks/use-ingredient-search";
import { dotClass } from "@/lib/ingredient-category";
import { cn } from "@/lib/utils";
import type { IngredientSuggestion } from "@/types/api";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

interface Props {
  /** Canonical names already in the pantry (shown checked + disabled). */
  existing: Set<string>;
  onAdd: (s: IngredientSuggestion) => void;
}

export function IngredientCombobox({ existing, onAdd }: Props) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const debounced = useDebounced(q.trim(), 180);
  const { data, isFetching } = useIngredientSearch(debounced);
  const results = data ?? [];

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setQ("");
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className="w-full gap-2 sm:w-auto">
          <Plus className="size-4" />
          Add an ingredient
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(18rem,calc(100vw-2rem))]" align="start">
        {/* backend already filters — don't let cmdk re-filter */}
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search ingredients…"
            value={q}
            onValueChange={setQ}
          />
          <CommandList>
            {debounced.length < 1 && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Start typing to find an ingredient.
              </p>
            )}
            {debounced.length >= 1 && !isFetching && results.length === 0 && (
              <CommandEmpty>No matching ingredient.</CommandEmpty>
            )}
            {results.map((s) => {
              const already = existing.has(s.name);
              return (
                <CommandItem
                  key={s.name}
                  value={s.name}
                  disabled={already}
                  onSelect={() => {
                    if (already) return;
                    onAdd(s);
                    setQ("");
                  }}
                >
                  <span
                    className={cn("size-2 shrink-0 rounded-full", dotClass(s.category))}
                    aria-hidden
                  />
                  <span className="flex-1">
                    {s.name}
                    {s.is_group ? (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        any {s.members && s.members.length > 0
                          ? `· ${s.members.length} kinds`
                          : ""}
                      </span>
                    ) : (
                      s.matched_alias && (
                        <span className="ml-1.5 text-xs text-muted-foreground">
                          matches “{s.matched_alias}”
                        </span>
                      )
                    )}
                  </span>
                  {already && <Check className="size-4 text-primary" />}
                </CommandItem>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
