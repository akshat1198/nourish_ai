import Link from "next/link";
import { FilterFlow } from "@/components/filters/filter-flow";
import { KitchenStatus } from "@/components/kitchen-status";
import { PantryManager } from "@/components/pantry/pantry-manager";
import { UserMenu } from "@/components/user-menu";

export default function AppPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="mx-auto flex w-full max-w-3xl items-center justify-between px-6 py-5">
        <Link href="/" className="font-display text-2xl font-semibold tracking-tight">
          Nourish<span className="text-primary">AI</span>
        </Link>
        <div className="flex items-center gap-4">
          <KitchenStatus />
          <UserMenu />
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 space-y-8 px-6 py-8">
        <div>
          <h1 className="font-display text-4xl font-semibold tracking-tight">
            Your kitchen
          </h1>
          <p className="mt-2 text-muted-foreground">
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
