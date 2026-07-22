"use client";

import { Check, CookingPot, ThumbsDown, ThumbsUp } from "lucide-react";
import { useFeedback } from "@/lib/hooks/use-feedback";
import { useRecipeFeedback } from "@/lib/hooks/use-user-feedback";
import { cn } from "@/lib/utils";

// Feedback bar under the recipe header: "Made this" toggle + thumbs up/down.
// State is derived server-side (append-only log); the optimistic fill is the
// confirmation. A rating click on the active thumb clears it (posts "unrated").
export function RecipeActions({ recipeId }: { recipeId: number }) {
  const { made, rating } = useRecipeFeedback(recipeId);
  const feedback = useFeedback(recipeId);
  const send = feedback.mutate;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ActionButton
        active={made}
        onClick={() => send(made ? "uncooked" : "cooked")}
        aria-pressed={made}
        aria-label={made ? "Unmark as made" : "Mark as made"}
      >
        {made ? <Check className="size-4" /> : <CookingPot className="size-4" />}
        {made ? "Made this" : "Made this?"}
      </ActionButton>

      <div className="flex items-center gap-1">
        <ActionButton
          active={rating === "liked"}
          onClick={() => send(rating === "liked" ? "unrated" : "liked")}
          aria-pressed={rating === "liked"}
          aria-label="Like this recipe"
          icon
        >
          <ThumbsUp className="size-4" />
        </ActionButton>
        <ActionButton
          active={rating === "disliked"}
          onClick={() => send(rating === "disliked" ? "unrated" : "disliked")}
          aria-pressed={rating === "disliked"}
          aria-label="Dislike this recipe"
          icon
          danger
        >
          <ThumbsDown className="size-4" />
        </ActionButton>
      </div>
    </div>
  );
}

function ActionButton({
  active,
  danger,
  icon,
  className,
  children,
  ...props
}: {
  active?: boolean;
  danger?: boolean;
  icon?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex h-9 touch-manipulation items-center justify-center gap-1.5 rounded-full border text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        icon ? "w-9" : "px-3.5",
        active && !danger && "border-primary bg-primary/10 text-primary",
        active && danger && "border-destructive/40 bg-destructive/10 text-destructive",
        !active && "border-border bg-card text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
