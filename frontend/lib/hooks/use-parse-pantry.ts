"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

// Free-text → recognized pantry items (LLM parse on the backend). The caller
// merges the recognized items into the pantry via the pantry PUT.
export function useParsePantry() {
  return useMutation({
    mutationFn: (text: string) => api.parsePantry(text),
  });
}
