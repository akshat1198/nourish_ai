"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

// Pantry photos → recognized pantry items (vision parse on the backend). The
// caller merges the recognized items into the pantry via the pantry PUT.
export function useParsePantryImages() {
  return useMutation({
    mutationFn: (files: File[]) => api.parsePantryImages(files),
  });
}
