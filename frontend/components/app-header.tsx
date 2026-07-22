import Link from "next/link";
import { KitchenStatus } from "@/components/kitchen-status";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

// Shared chrome for every page in the `/app` flow (pantry, filter steps,
// results, saved, plans). Lifted out of the old single `/app` page so the
// segment layout owns it and it doesn't re-mount between pages.
export function AppHeader() {
  return (
    <header className="relative mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-5">
      <div className="flex items-center gap-5">
        <Link
          href="/"
          className="font-display text-2xl font-semibold tracking-tight"
        >
          Nourish<span className="text-primary">AI</span>
        </Link>
        <nav className="hidden items-center gap-4 text-sm text-muted-foreground sm:flex">
          <Link href="/app" className="transition-colors hover:text-foreground">
            Kitchen
          </Link>
          <Link href="/app/saved" className="transition-colors hover:text-foreground">
            Saved
          </Link>
          <Link href="/app/plans" className="transition-colors hover:text-foreground">
            Plans
          </Link>
        </nav>
      </div>
      <div className="flex items-center gap-3">
        <KitchenStatus />
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
