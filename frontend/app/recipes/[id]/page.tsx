import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { RecipeDetailView } from "@/components/recipe/recipe-detail";

// Thin server shell: parse the id, then hand off to the client view. Fetching
// stays client-side because apiFetch reads the auth identity from the browser
// session (Bearer / X-User-Key), matching the app's TanStack pattern.
export default async function RecipePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const recipeId = Number(id);

  if (!Number.isInteger(recipeId) || recipeId <= 0) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-2xl flex-col justify-center px-6">
        <Link
          href="/app"
          className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back to your kitchen
        </Link>
        <h1 className="font-display text-4xl font-semibold tracking-tight">
          Recipe not found
        </h1>
        <p className="mt-3 text-muted-foreground">
          That doesn&apos;t look like a valid recipe link.
        </p>
      </div>
    );
  }

  return <RecipeDetailView id={recipeId} />;
}
