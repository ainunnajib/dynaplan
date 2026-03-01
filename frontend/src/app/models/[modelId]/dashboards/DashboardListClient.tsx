"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getDashboards, createDashboard, deleteDashboard } from "@/lib/api";
import type { Dashboard } from "@/lib/api";

interface Props {
  modelId: string;
}

export default function DashboardListClient({ modelId }: Props) {
  const router = useRouter();
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDashboards(modelId);
      setDashboards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboards");
    } finally {
      setIsLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate() {
    if (!createName.trim()) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      const dash = await createDashboard(modelId, {
        name: createName.trim(),
        description: createDescription.trim() || undefined,
      });
      setDashboards((prev) => [...prev, dash]);
      setShowCreateDialog(false);
      setCreateName("");
      setCreateDescription("");
      router.push(`/models/${modelId}/dashboards/${dash.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create dashboard");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDelete(dashboardId: string) {
    try {
      await deleteDashboard(dashboardId);
      setDashboards((prev) => prev.filter((d) => d.id !== dashboardId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete dashboard");
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-800">
          All Dashboards
          {dashboards.length > 0 && (
            <span className="ml-2 text-sm font-normal text-zinc-500">
              ({dashboards.length})
            </span>
          )}
        </h2>
        <button
          type="button"
          onClick={() => setShowCreateDialog(true)}
          className="flex items-center gap-2 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
        >
          <PlusIcon className="h-4 w-4" />
          New Dashboard
        </button>
      </div>

      {dashboards.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white py-16 text-center">
          <DashboardIcon className="h-10 w-10 text-zinc-300" />
          <h3 className="mt-3 text-sm font-medium text-zinc-600">No dashboards yet</h3>
          <p className="mt-1 text-xs text-zinc-400 max-w-xs">
            Create a dashboard to visualize your model data with charts, KPI cards, and more.
          </p>
          <button
            type="button"
            onClick={() => setShowCreateDialog(true)}
            className="mt-4 flex items-center gap-2 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            New Dashboard
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {dashboards.map((dash) => (
            <DashboardCard
              key={dash.id}
              dashboard={dash}
              modelId={modelId}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {showCreateDialog && (
        <CreateDashboardDialog
          createName={createName}
          createDescription={createDescription}
          isCreating={isCreating}
          createError={createError}
          onNameChange={setCreateName}
          onDescriptionChange={setCreateDescription}
          onCreate={handleCreate}
          onClose={() => {
            setShowCreateDialog(false);
            setCreateName("");
            setCreateDescription("");
            setCreateError(null);
          }}
        />
      )}
    </div>
  );
}

function DashboardCard({
  dashboard,
  modelId,
  onDelete,
}: {
  dashboard: Dashboard;
  modelId: string;
  onDelete: (id: string) => void;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleDelete() {
    setIsDeleting(true);
    await onDelete(dashboard.id);
    setIsDeleting(false);
    setShowDeleteConfirm(false);
  }

  return (
    <div className="group relative rounded-lg border border-zinc-200 bg-white p-5 shadow-sm hover:border-zinc-300 hover:shadow-md transition-all">
      <div className="flex items-start justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
          <DashboardIcon className="h-5 w-5" />
        </div>
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          {dashboard.is_published && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
              Published
            </span>
          )}
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="rounded p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 transition-colors"
            title="Delete dashboard"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      <h3 className="mt-3 text-sm font-semibold text-zinc-900">{dashboard.name}</h3>
      {dashboard.description && (
        <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{dashboard.description}</p>
      )}

      <div className="mt-4 border-t border-zinc-100 pt-4">
        <Link
          href={`/models/${modelId}/dashboards/${dashboard.id}`}
          className="flex items-center gap-1.5 rounded-md bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 transition-colors w-fit"
        >
          <EditIcon className="h-3.5 w-3.5" />
          Open Dashboard
        </Link>
      </div>

      {showDeleteConfirm && (
        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-lg bg-white/95 p-4 text-center backdrop-blur-sm">
          <ExclamationIcon className="h-6 w-6 text-red-500" />
          <p className="mt-2 text-sm font-semibold text-zinc-800">Delete dashboard?</p>
          <p className="mt-1 text-xs text-zinc-500">
            <span className="font-medium">{dashboard.name}</span> and all its widgets will be permanently removed.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              disabled={isDeleting}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CreateDashboardDialog({
  createName,
  createDescription,
  isCreating,
  createError,
  onNameChange,
  onDescriptionChange,
  onCreate,
  onClose,
}: {
  createName: string;
  createDescription: string;
  isCreating: boolean;
  createError: string | null;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onCreate: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-base font-semibold text-zinc-900">New Dashboard</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Give your dashboard a name and optional description.
        </p>

        <div className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={createName}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="e.g. Q1 Sales Overview"
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") onCreate();
              }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1">
              Description
            </label>
            <textarea
              value={createDescription}
              onChange={(e) => onDescriptionChange(e.target.value)}
              placeholder="Optional description..."
              rows={2}
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 resize-none"
            />
          </div>
        </div>

        {createError && (
          <p className="mt-3 text-xs text-red-600">{createError}</p>
        )}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isCreating}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onCreate}
            disabled={isCreating || !createName.trim()}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {isCreating ? "Creating..." : "Create Dashboard"}
          </button>
        </div>
      </div>
    </div>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function DashboardIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function EditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
    </svg>
  );
}

function ExclamationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  );
}
