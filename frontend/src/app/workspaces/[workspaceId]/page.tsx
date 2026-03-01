import Link from "next/link";
import { getModels, getWorkspaceQuotaUsage, fetchApi } from "@/lib/api";
import { getModelStatus } from "@/lib/api";
import type { PlanningModel, Workspace, WorkspaceQuotaUsage } from "@/lib/api";
import WorkspaceQuotaDashboard from "@/components/workspace/WorkspaceQuotaDashboard";

export const metadata = {
  title: "Workspace — Dynaplan",
};

interface PageProps {
  params: Promise<{ workspaceId: string }>;
}

export default async function WorkspacePage({ params }: PageProps) {
  const { workspaceId } = await params;

  let workspace: Workspace | null = null;
  let models: PlanningModel[] = [];
  let quotaUsage: WorkspaceQuotaUsage | null = null;
  let fetchError: string | null = null;

  try {
    [workspace, models, quotaUsage] = await Promise.all([
      fetchApi<Workspace>(`/api/workspaces/${workspaceId}`),
      getModels(workspaceId),
      getWorkspaceQuotaUsage(workspaceId),
    ]);
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load workspace";
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto max-w-5xl">
          <nav className="mb-1 flex items-center gap-1 text-xs text-zinc-500">
            <Link href="/workspaces" className="hover:text-zinc-800">
              Workspaces
            </Link>
            <span>/</span>
            <span className="text-zinc-800">{workspace?.name ?? workspaceId}</span>
          </nav>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-zinc-900">
                {workspace?.name ?? "Workspace"}
              </h1>
              {workspace?.description && (
                <p className="text-sm text-zinc-500">{workspace.description}</p>
              )}
            </div>
            <Link
              href={`/workspaces/${workspaceId}/models/new`}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create Model
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : (
          <>
            {quotaUsage && <WorkspaceQuotaDashboard usage={quotaUsage} />}
            {models.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white py-16 text-center">
                <ModelIcon />
                <h2 className="mt-4 text-base font-medium text-zinc-700">No models yet</h2>
                <p className="mt-1 text-sm text-zinc-500">
                  Create a planning model to get started.
                </p>
                <Link
                  href={`/workspaces/${workspaceId}/models/new`}
                  className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                >
                  Create your first model
                </Link>
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {models.map((model) => (
                  <ModelCard key={model.id} model={model} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function ModelCard({ model }: { model: PlanningModel }) {
  const status = getModelStatus(model);
  const statusColors: Record<"active" | "archived", string> = {
    active: "bg-green-100 text-green-700",
    archived: "bg-zinc-100 text-zinc-500",
  };

  return (
    <Link
      href={`/models/${model.id}`}
      className="group block rounded-lg border border-zinc-200 bg-white p-5 shadow-sm hover:border-blue-300 hover:shadow-md transition-all"
    >
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
          <ModelIcon />
        </div>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[status]}`}
        >
          {status}
        </span>
      </div>
      <h2 className="mt-3 text-sm font-semibold text-zinc-900">{model.name}</h2>
      {model.description && (
        <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{model.description}</p>
      )}
      <p className="mt-3 text-xs text-zinc-400">
        Updated {new Date(model.updated_at).toLocaleDateString()}
      </p>
    </Link>
  );
}

function ModelIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h1.5C5.496 19.5 6 18.996 6 18.375m-3.75.125V9.75M3.375 19.5A2.25 2.25 0 0 0 1.5 17.625M1.5 9.75V5.25A2.25 2.25 0 0 1 3.75 3h16.5A2.25 2.25 0 0 1 22.5 5.25v4.5M1.5 9.75h19.5M22.5 9.75v8.625A2.25 2.25 0 0 1 20.25 20.5H3.75" />
    </svg>
  );
}
