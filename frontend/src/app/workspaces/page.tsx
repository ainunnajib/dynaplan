import Link from "next/link";
import { getWorkspaces } from "@/lib/api";
import type { Workspace } from "@/lib/api";

export const metadata = {
  title: "Workspaces — Dynaplan",
};

export default async function WorkspacesPage() {
  let workspaces: Workspace[] = [];
  let fetchError: string | null = null;

  try {
    workspaces = await getWorkspaces();
  } catch (err) {
    fetchError = err instanceof Error ? err.message : "Failed to load workspaces";
  }

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-zinc-900">Workspaces</h1>
            <p className="text-sm text-zinc-500">Your planning workspaces</p>
          </div>
          <Link
            href="/workspaces/new"
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Create Workspace
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {fetchError ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {fetchError}
          </div>
        ) : workspaces.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white py-16 text-center">
            <WorkspaceIcon />
            <h2 className="mt-4 text-base font-medium text-zinc-700">No workspaces yet</h2>
            <p className="mt-1 text-sm text-zinc-500">
              Create a workspace to start building planning models.
            </p>
            <Link
              href="/workspaces/new"
              className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Create your first workspace
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {workspaces.map((ws) => (
              <WorkspaceCard key={ws.id} workspace={ws} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function WorkspaceCard({ workspace }: { workspace: Workspace }) {
  return (
    <Link
      href={`/workspaces/${workspace.id}`}
      className="group block rounded-lg border border-zinc-200 bg-white p-5 shadow-sm hover:border-blue-300 hover:shadow-md transition-all"
    >
      <div className="flex items-start justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
          <WorkspaceIcon />
        </div>
        <ArrowRightIcon className="mt-1 h-4 w-4 text-zinc-400 opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <h2 className="mt-3 text-sm font-semibold text-zinc-900">{workspace.name}</h2>
      {workspace.description && (
        <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{workspace.description}</p>
      )}
      <p className="mt-3 text-xs text-zinc-400">
        Created {new Date(workspace.created_at).toLocaleDateString()}
      </p>
    </Link>
  );
}

function WorkspaceIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v8.25A2.25 2.25 0 0 0 4.5 16.5h15a2.25 2.25 0 0 0 2.25-2.25V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
    </svg>
  );
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
    </svg>
  );
}
