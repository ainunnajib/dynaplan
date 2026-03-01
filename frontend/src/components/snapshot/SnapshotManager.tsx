"use client";

import { useState, useEffect, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SnapshotMetadata {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
}

interface RestoreResult {
  snapshot_id: string;
  model_id: string;
  entities_restored: Record<string, number>;
}

interface SnapshotManagerProps {
  modelId: string;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SnapshotManager({ modelId }: SnapshotManagerProps) {
  const [snapshots, setSnapshots] = useState<SnapshotMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [restoreResult, setRestoreResult] = useState<RestoreResult | null>(null);

  async function loadSnapshots() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<SnapshotMetadata[]>(
        `/api/models/${modelId}/snapshots`
      );
      setSnapshots(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load snapshots");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadSnapshots();
  }, [modelId]);

  async function handleDelete(snapshotId: string) {
    try {
      await fetchApi(`/api/snapshots/${snapshotId}`, { method: "DELETE" });
      setSnapshots((prev) => prev.filter((s) => s.id !== snapshotId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete snapshot");
    }
  }

  async function handleRestore(snapshotId: string) {
    try {
      const result = await fetchApi<RestoreResult>(
        `/api/snapshots/${snapshotId}/restore`,
        { method: "POST" }
      );
      setRestoreResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restore snapshot");
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">Model Snapshots</h2>
          <p className="text-sm text-zinc-500">
            Create and manage named snapshots of this model's state.
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          type="button"
        >
          Create Snapshot
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 font-medium underline"
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Restore result banner */}
      {restoreResult && (
        <RestoreResultBanner
          result={restoreResult}
          onDismiss={() => setRestoreResult(null)}
        />
      )}

      {/* Create snapshot form */}
      {showCreateForm && (
        <CreateSnapshotForm
          modelId={modelId}
          onCreated={(snap) => {
            setSnapshots((prev) => [snap, ...prev]);
            setShowCreateForm(false);
          }}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {/* Snapshot list */}
      {isLoading ? (
        <div className="py-8 text-center text-sm text-zinc-400">
          Loading snapshots...
        </div>
      ) : snapshots.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 py-12 text-center">
          <SnapshotIcon className="mx-auto h-10 w-10 text-zinc-300" />
          <p className="mt-3 text-sm text-zinc-500">No snapshots yet.</p>
          <p className="mt-1 text-xs text-zinc-400">
            Create a snapshot to capture the current state of this model.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {snapshots.map((snap) => (
            <SnapshotCard
              key={snap.id}
              snapshot={snap}
              onDelete={handleDelete}
              onRestore={handleRestore}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Create form ───────────────────────────────────────────────────────────────

function CreateSnapshotForm({
  modelId,
  onCreated,
  onCancel,
}: {
  modelId: string;
  onCreated: (snap: SnapshotMetadata) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Snapshot name is required");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const snap = await fetchApi<SnapshotMetadata>(
        `/api/models/${modelId}/snapshots`,
        {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            description: description.trim() || null,
          }),
        }
      );
      onCreated(snap);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create snapshot");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-5">
      <h3 className="mb-4 text-sm font-semibold text-zinc-800">New Snapshot</h3>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label
            htmlFor="snap-name"
            className="block text-xs font-medium text-zinc-700"
          >
            Name <span className="text-red-500">*</span>
          </label>
          <input
            id="snap-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Before Q1 reforecast"
            className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            autoFocus
            disabled={isSubmitting}
          />
        </div>
        <div>
          <label
            htmlFor="snap-desc"
            className="block text-xs font-medium text-zinc-700"
          >
            Description{" "}
            <span className="font-normal text-zinc-400">(optional)</span>
          </label>
          <textarea
            id="snap-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What changed or why this snapshot was taken"
            rows={2}
            className="mt-1 block w-full resize-none rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={isSubmitting}
          />
        </div>
        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
          </p>
        )}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting || !name.trim()}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Creating..." : "Create Snapshot"}
          </button>
        </div>
      </form>
    </div>
  );
}

// ── Snapshot card ─────────────────────────────────────────────────────────────

function SnapshotCard({
  snapshot,
  onDelete,
  onRestore,
}: {
  snapshot: SnapshotMetadata;
  onDelete: (id: string) => void;
  onRestore: (id: string) => void;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);

  const formattedDate = new Date(snapshot.created_at).toLocaleString();

  async function confirmDelete() {
    setIsDeleting(true);
    await onDelete(snapshot.id);
    setIsDeleting(false);
    setShowDeleteConfirm(false);
  }

  async function confirmRestore() {
    setIsRestoring(true);
    await onRestore(snapshot.id);
    setIsRestoring(false);
    setShowRestoreConfirm(false);
  }

  return (
    <div className="relative rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
            <SnapshotIcon className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-900">{snapshot.name}</p>
            {snapshot.description && (
              <p className="mt-0.5 text-xs text-zinc-500">{snapshot.description}</p>
            )}
            <p className="mt-1 text-xs text-zinc-400">{formattedDate}</p>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-shrink-0 items-center gap-2">
          <button
            onClick={() => setShowRestoreConfirm(true)}
            className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
            type="button"
          >
            Restore
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="rounded-md border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-500 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors"
            type="button"
          >
            Delete
          </button>
        </div>
      </div>

      {/* Delete confirmation overlay */}
      {showDeleteConfirm && (
        <ConfirmOverlay
          title="Delete this snapshot?"
          message={`"${snapshot.name}" will be permanently deleted.`}
          confirmLabel="Delete"
          confirmClass="bg-red-600 hover:bg-red-700"
          isLoading={isDeleting}
          onConfirm={confirmDelete}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}

      {/* Restore confirmation overlay */}
      {showRestoreConfirm && (
        <ConfirmOverlay
          title="Restore this snapshot?"
          message={`The model will be reverted to "${snapshot.name}". Current state will be overwritten.`}
          confirmLabel="Restore"
          confirmClass="bg-emerald-600 hover:bg-emerald-700"
          isLoading={isRestoring}
          onConfirm={confirmRestore}
          onCancel={() => setShowRestoreConfirm(false)}
        />
      )}
    </div>
  );
}

// ── Confirm overlay ───────────────────────────────────────────────────────────

function ConfirmOverlay({
  title,
  message,
  confirmLabel,
  confirmClass,
  isLoading,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  confirmClass: string;
  isLoading: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-lg bg-white/96 p-4 text-center backdrop-blur-sm">
      <p className="text-sm font-semibold text-zinc-800">{title}</p>
      <p className="mt-1 text-xs text-zinc-500">{message}</p>
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onCancel}
          disabled={isLoading}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          type="button"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className={`rounded-md px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 transition-colors ${confirmClass}`}
          type="button"
        >
          {isLoading ? "Processing..." : confirmLabel}
        </button>
      </div>
    </div>
  );
}

// ── Restore result banner ─────────────────────────────────────────────────────

function RestoreResultBanner({
  result,
  onDismiss,
}: {
  result: RestoreResult;
  onDismiss: () => void;
}) {
  return (
    <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-emerald-800">
            Snapshot restored successfully
          </p>
          <div className="mt-1 flex flex-wrap gap-2">
            {Object.entries(result.entities_restored).map(([type, count]) => (
              <span
                key={type}
                className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700"
              >
                {count} {type}
              </span>
            ))}
          </div>
        </div>
        <button
          onClick={onDismiss}
          className="text-xs font-medium text-emerald-700 underline"
          type="button"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function SnapshotIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z"
      />
    </svg>
  );
}
