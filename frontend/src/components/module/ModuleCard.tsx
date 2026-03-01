"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchApi } from "@/lib/api";
import type { Module } from "@/lib/api";

interface ModuleCardProps {
  module: Module;
  modelId: string;
  lineItemCount?: number;
}

export default function ModuleCard({ module, modelId, lineItemCount }: ModuleCardProps) {
  const router = useRouter();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handleDelete() {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await fetchApi(`/api/modules/${module.id}`, { method: "DELETE" });
      router.refresh();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Delete failed");
      setIsDeleting(false);
    }
  }

  return (
    <div className="group relative rounded-lg border border-zinc-200 bg-white p-5 shadow-sm hover:border-zinc-300 hover:shadow-md transition-all">
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
          <CubeIcon className="h-5 w-5" />
        </div>
        {/* Actions — visible on hover */}
        <div className="flex items-center gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100">
          <Link
            href={`/models/${modelId}/modules/${module.id}/edit`}
            className="rounded p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors"
            title="Edit module"
          >
            <PencilIcon className="h-4 w-4" />
          </Link>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="rounded p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600 transition-colors"
            title="Delete module"
            type="button"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Module info */}
      <h3 className="mt-3 text-sm font-semibold text-zinc-900">{module.name}</h3>
      {module.description && (
        <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{module.description}</p>
      )}

      {lineItemCount !== undefined && (
        <p className="mt-2 text-xs text-zinc-400">
          {lineItemCount} line {lineItemCount === 1 ? "item" : "items"}
        </p>
      )}

      {/* Navigation links */}
      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-zinc-100 pt-4">
        <Link
          href={`/models/${modelId}/modules/${module.id}`}
          className="flex w-full items-center justify-center gap-1.5 rounded-md bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-100 sm:w-auto sm:justify-start"
        >
          <GridIcon className="h-3.5 w-3.5" />
          Grid View
        </Link>
        <Link
          href={`/models/${modelId}/blueprint#module-${module.id}`}
          className="flex w-full items-center justify-center gap-1.5 rounded-md bg-zinc-50 px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-100 sm:w-auto sm:justify-start"
        >
          <BlueprintIcon className="h-3.5 w-3.5" />
          Blueprint
        </Link>
      </div>

      {/* Delete confirmation */}
      {showDeleteConfirm && (
        <DeleteConfirmOverlay
          moduleName={module.name}
          isDeleting={isDeleting}
          deleteError={deleteError}
          onConfirm={handleDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setDeleteError(null);
          }}
        />
      )}
    </div>
  );
}

function DeleteConfirmOverlay({
  moduleName,
  isDeleting,
  deleteError,
  onConfirm,
  onCancel,
}: {
  moduleName: string;
  isDeleting: boolean;
  deleteError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-lg bg-white/95 p-4 text-center backdrop-blur-sm">
      <ExclamationIcon className="h-6 w-6 text-red-500" />
      <p className="mt-2 text-sm font-semibold text-zinc-800">Delete module?</p>
      <p className="mt-1 text-xs text-zinc-500">
        <span className="font-medium">{moduleName}</span> and all its line items will be
        permanently removed.
      </p>
      {deleteError && (
        <p className="mt-2 text-xs text-red-600">{deleteError}</p>
      )}
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onCancel}
          disabled={isDeleting}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          type="button"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={isDeleting}
          className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
          type="button"
        >
          {isDeleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </div>
  );
}

function CubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
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

function GridIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 1.5v-1.5m0 0c0-.621.504-1.125 1.125-1.125m-1.125 2.625c0-.621.504-1.125 1.125-1.125" />
    </svg>
  );
}

function BlueprintIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25ZM6.75 12h.008v.008H6.75V12Zm0 3h.008v.008H6.75V15Zm0 3h.008v.008H6.75V18Z" />
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
