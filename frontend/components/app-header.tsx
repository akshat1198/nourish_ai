import Link from "next/link";
import { KitchenStatus } from "@/components/kitchen-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

// Shared chrome for every page in the `/app` flow (pantry, filter steps,
// results). Lifted out of the old single `/app` page so the segment layout
// owns it and it doesn't re-mount between steps.
export function AppHeader() {
  return (
    <header className="relative mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-5">
      <Link
        href="/"
        className="font-display text-2xl font-semibold tracking-tight"
      >
        Nourish<span className="text-primary">AI</span>
      </Link>
      <div className="flex items-center gap-3">
        <KitchenStatus />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
