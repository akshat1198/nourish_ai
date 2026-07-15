import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function OptionPill({
  selected,
  onClick,
  disabled,
  children,
  className,
}: {
  selected?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={selected}
      className={cn(
        "inline-flex h-10 items-center gap-1.5 rounded-full border px-4 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        disabled
          ? "cursor-not-allowed border-border bg-card text-muted-foreground opacity-45"
          : "cursor-pointer",
        selected
          ? "border-primary bg-primary/10 font-medium text-primary"
          : "border-border bg-card text-foreground hover:bg-secondary/60",
        className,
      )}
    >
      {selected && <Check className="size-3.5" />}
      {children}
    </button>
  );
}
