import Link from "next/link";
import { ArrowLeft } from "lucide-react";

// Seam for Stage 7 — full recipe detail (fetch the source, scale servings,
// substitution-aware edits). For now, a stub.
export default async function RecipePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center px-6">
      <Link
        href="/app"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to your kitchen
      </Link>
      <h1 className="font-display text-4xl font-semibold tracking-tight">
        Recipe #{id}
      </h1>
      <p className="mt-3 max-w-md text-muted-foreground">
        Full recipe steps, serving-size scaling, and substitution-aware edits are
        coming next. For now, head back and keep building your list.
      </p>
    </div>
  );
}
