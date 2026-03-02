import Link from "next/link";
import { getModel, type PlanningModel } from "@/lib/api";
import UXAppBuilderClient from "@/components/ux-pages/UXAppBuilderClient";

export const metadata = {
  title: "App Builder — Dynaplan",
};

interface PageProps {
  params: Promise<{ modelId: string; pageId: string }>;
}

export default async function AppBuilderPage({ params }: PageProps) {
  const { modelId, pageId } = await params;

  let model: PlanningModel | null = null;
  let fetchError: string | null = null;

  try {
    model = await getModel(modelId);
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load model";
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-3 py-4 sm:px-4 md:px-6">
        <div className="mx-auto max-w-7xl">
          <nav className="mb-1 flex flex-wrap items-center gap-1 text-xs text-zinc-500">
            <Link href="/workspaces" className="hover:text-zinc-800">
              Workspaces
            </Link>
            {model && (
              <>
                <span>/</span>
                <Link
                  href={`/workspaces/${model.workspace_id}`}
                  className="hover:text-zinc-800"
                >
                  Workspace
                </Link>
                <span>/</span>
                <Link href={`/models/${modelId}`} className="hover:text-zinc-800">
                  {model.name}
                </Link>
              </>
            )}
            <span>/</span>
            <Link href={`/models/${modelId}/apps`} className="hover:text-zinc-800">
              Apps
            </Link>
            <span>/</span>
            <span className="text-zinc-800">{pageId}</span>
          </nav>
          <div>
            <h1 className="text-xl font-semibold text-zinc-900">App Builder</h1>
            <p className="text-sm text-zinc-500">
              Configure navigation, context selectors, and linked cards.
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-3 py-6 sm:px-4 sm:py-8 md:px-6">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : (
          <UXAppBuilderClient modelId={modelId} pageId={pageId} />
        )}
      </main>
    </div>
  );
}
