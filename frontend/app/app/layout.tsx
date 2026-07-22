import type { ReactNode } from "react";
import { AppHeader } from "@/components/app-header";
import { PageTransition } from "@/components/filters/page-transition";
import { FilterFlowProvider } from "@/lib/flow/filter-flow-context";

// Shared shell for the whole discovery flow (pantry → filter steps → review →
// results). The provider lives here so answers survive navigation between the
// child pages; the aurora + header stay put while only the page content slides.
export default function AppLayout({ children }: { children: ReactNode }) {
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

      <FilterFlowProvider>
        <AppHeader />
        <main className="relative mx-auto w-full max-w-3xl flex-1 px-6 py-10">
          <PageTransition>{children}</PageTransition>
        </main>
      </FilterFlowProvider>
    </div>
  );
}
