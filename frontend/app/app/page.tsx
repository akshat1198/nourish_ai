import Link from "next/link";
import { FilterFlow } from "@/components/filters/filter-flow";
import { KitchenStatus } from "@/components/kitchen-status";
import { PantryManager } from "@/components/pantry/pantry-manager";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/user-menu";

export default function AppPage() {
  return (
    <div className="relative flex min-h-dvh flex-col">
      {/* ambient aurora at the top — the landing's through-line, kept subtle
          behind the tool. Fades into the page before the cards. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[560px] overflow-hidden"
      >
        <div className="animate-aurora absolute -left-24 -top-40 size-[40rem] rounded-full bg-primary/25 blur-[120px]" />
        <div className="animate-aurora absolute -right-28 -top-24 size-[34rem] rounded-full bg-turmeric/25 blur-[120px] [animation-delay:-6s]" />
        <div className="animate-aurora absolute left-1/3 -top-16 size-[26rem] rounded-full bg-primary/15 blur-[110px] [animation-delay:-11s]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-background" />
      </div>

      <header className="relative mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-5">
        <Link href="/" className="font-display text-2xl font-semibold tracking-tight">
          Nourish<span className="text-primary">AI</span>
        </Link>
        <div className="flex items-center gap-3">
          <KitchenStatus />
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      <main className="relative mx-auto w-full max-w-3xl flex-1 space-y-8 px-6 py-10">
        <div>
          <h1 className="font-display text-5xl font-semibold tracking-tight">
            Your kitchen
          </h1>
          <p className="mt-3 text-lg text-muted-foreground">
            Keep your pantry current — then tell us what you&apos;re in the mood
            for.
          </p>
        </div>

        <PantryManager />
        <FilterFlow />
      </main>
    </div>
  );
}
