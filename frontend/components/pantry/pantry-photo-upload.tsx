"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, ImageIcon, Loader2, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { compressImage } from "@/lib/image-resize";

// Matches the server cap so a batch that would 400 never leaves the browser.
const MAX_PHOTOS = 6;

interface Staged {
  file: File;
  previewUrl: string;
  // HEIC has no browser-renderable preview, and decoding one just to draw a
  // 64px tile would pull in the wasm decoder on every pick. Fall back to a
  // labelled tile instead; the file still converts fine on analyze.
  previewBroken?: boolean;
}

/**
 * Stages pantry photos and hands them to the parent to analyze. Owns only the
 * picker and its thumbnails — merging results into the pantry stays with the
 * parent, the same split the free-text intake used.
 */
export function PantryPhotoUpload({
  onAnalyze,
  isAnalyzing,
  onUnsupported,
}: {
  onAnalyze: (files: File[]) => Promise<void>;
  isAnalyzing: boolean;
  onUnsupported: (names: string[]) => void;
}) {
  const [staged, setStaged] = useState<Staged[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Object URLs outlive the component unless explicitly released.
  useEffect(
    () => () => staged.forEach((s) => URL.revokeObjectURL(s.previewUrl)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const addFiles = (files: FileList | null) => {
    if (!files) return;
    const room = MAX_PHOTOS - staged.length;
    const next = Array.from(files)
      .slice(0, Math.max(room, 0))
      .map((file) => ({ file, previewUrl: URL.createObjectURL(file) }));
    setStaged((s) => [...s, ...next]);
    // Reset so re-picking the same file still fires a change event.
    if (inputRef.current) inputRef.current.value = "";
  };

  const removeAt = (index: number) =>
    setStaged((s) => {
      URL.revokeObjectURL(s[index].previewUrl);
      return s.filter((_, i) => i !== index);
    });

  const clear = () => {
    staged.forEach((s) => URL.revokeObjectURL(s.previewUrl));
    setStaged([]);
  };

  const analyze = async () => {
    const prepared = await Promise.all(
      staged.map(async (s) => ({ name: s.file.name, out: await compressImage(s.file) })),
    );
    const usable = prepared.filter((p) => p.out).map((p) => p.out as File);
    const rejected = prepared.filter((p) => !p.out).map((p) => p.name);
    if (rejected.length) onUnsupported(rejected);
    if (!usable.length) return;

    try {
      await onAnalyze(usable);
      clear();
    } catch {
      // Parent shows the error; keep the photos staged so retry is one tap.
    }
  };

  return (
    <div className="space-y-2">
      {/* .heic/.heif by extension too: macOS often reports no MIME type for them. */}
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
        multiple
        className="hidden"
        onChange={(e) => addFiles(e.target.files)}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-1.5"
          disabled={isAnalyzing || staged.length >= MAX_PHOTOS}
          onClick={() => inputRef.current?.click()}
        >
          <Camera className="size-3.5" />
          {staged.length ? "Add more" : "Snap your shelves"}
        </Button>

        {staged.length > 0 && (
          <Button
            type="button"
            size="sm"
            className="gap-1.5"
            disabled={isAnalyzing}
            onClick={analyze}
          >
            {isAnalyzing ? (
              <>
                <Loader2 className="size-3.5 animate-spin" />
                Reading photos…
              </>
            ) : (
              <>
                <Sparkles className="size-3.5" />
                Find ingredients
              </>
            )}
          </Button>
        )}

        <p className="text-xs text-muted-foreground">
          {staged.length
            ? `${staged.length} of ${MAX_PHOTOS} photos`
            : `Or photograph what you have — up to ${MAX_PHOTOS} shots of the fridge, shelf, or counter.`}
        </p>
      </div>

      {staged.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {staged.map((s, i) => (
            <li
              key={s.previewUrl}
              className="group relative size-16 overflow-hidden rounded-lg border border-border"
            >
              {s.previewBroken ? (
                <span className="flex size-full flex-col items-center justify-center gap-0.5 bg-secondary/50 px-1 text-center">
                  <ImageIcon className="size-4 text-muted-foreground" aria-hidden />
                  <span className="w-full truncate text-[9px] leading-tight text-muted-foreground">
                    {s.file.name}
                  </span>
                </span>
              ) : (
                /* Transient blob: URLs — nothing for next/image to optimize. */
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={s.previewUrl}
                  alt=""
                  className="size-full object-cover"
                  onError={() =>
                    setStaged((prev) =>
                      prev.map((p, idx) => (idx === i ? { ...p, previewBroken: true } : p)),
                    )
                  }
                />
              )}
              {!isAnalyzing && (
                <button
                  type="button"
                  onClick={() => removeAt(i)}
                  aria-label={`Remove ${s.file.name}`}
                  className="absolute right-0.5 top-0.5 rounded-full bg-foreground/70 p-0.5 text-background opacity-0 transition-opacity focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-hover:opacity-100"
                >
                  <X className="size-3" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
