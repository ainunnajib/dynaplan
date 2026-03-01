import Link from "next/link";
import { getModel } from "@/lib/api";
import type { PlanningModel } from "@/lib/api";
import DashboardViewClient from "./DashboardViewClient";

export const metadata = {
  title: "Dashboard — Dynaplan",
};

interface PageProps {
  params: Promise<{ modelId: string; dashboardId: string }>;
}

export default async function DashboardPage({ params }: PageProps) {
  const { modelId, dashboardId } = await params;

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
        <div className="mx-auto max-w-full">
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
            <Link
              href={`/models/${modelId}/dashboards`}
              className="hover:text-zinc-800"
            >
              Dashboards
            </Link>
            <span>/</span>
            <span className="text-zinc-800">Editor</span>
          </nav>
        </div>
      </header>

      {fetchError ? (
        <main className="mx-auto max-w-6xl px-3 py-6 sm:px-4 sm:py-8 md:px-6">
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        </main>
      ) : (
        <DashboardViewClient modelId={modelId} dashboardId={dashboardId} />
      )}
    </div>
  );
}
