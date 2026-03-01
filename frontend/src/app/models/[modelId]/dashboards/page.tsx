import Link from "next/link";
import { getModel } from "@/lib/api";
import type { PlanningModel } from "@/lib/api";
import DashboardListClient from "./DashboardListClient";

export const metadata = {
  title: "Dashboards — Dynaplan",
};

interface PageProps {
  params: Promise<{ modelId: string }>;
}

export default async function DashboardsPage({ params }: PageProps) {
  const { modelId } = await params;

  let model: PlanningModel | null = null;
  let fetchError: string | null = null;

  try {
    model = await getModel(modelId);
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load model";
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-6xl">
          <nav className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
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
                <Link
                  href={`/models/${modelId}`}
                  className="hover:text-zinc-800"
                >
                  {model.name}
                </Link>
              </>
            )}
            <span>/</span>
            <span className="text-zinc-800">Dashboards</span>
          </nav>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-zinc-900">Dashboards</h1>
              {model?.description && (
                <p className="text-sm text-zinc-500">{model.description}</p>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : (
          <DashboardListClient modelId={modelId} />
        )}
      </main>
    </div>
  );
}
