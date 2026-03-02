"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createUXPage,
  deleteUXPage,
  getUXPages,
  type UXPage,
  type UXPageType,
} from "@/lib/api";

interface UXAppListClientProps {
  modelId: string;
}

export default function UXAppListClient({ modelId }: UXAppListClientProps) {
  const router = useRouter();
  const [pages, setPages] = useState<UXPage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createType, setCreateType] = useState<UXPageType>("board");
  const [createParentId, setCreateParentId] = useState<string>("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadPages = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getUXPages(modelId);
      setPages(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pages");
    } finally {
      setIsLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    loadPages();
  }, [loadPages]);

  const pagesByParent = useMemo(() => {
    const groups = new Map<string, UXPage[]>();
    for (const page of pages) {
      const key = page.parent_page_id ?? "__root__";
      const list = groups.get(key) ?? [];
      list.push(page);
      groups.set(key, list);
    }

    for (const [, list] of groups) {
      list.sort((a, b) => {
        if (a.sort_order !== b.sort_order) {
          return a.sort_order - b.sort_order;
        }
        return a.name.localeCompare(b.name);
      });
    }

    return groups;
  }, [pages]);

  async function handleCreatePage() {
    if (!createName.trim()) {
      return;
    }

    setIsCreating(true);
    setCreateError(null);
    try {
      const created = await createUXPage(modelId, {
        name: createName.trim(),
        page_type: createType,
        parent_page_id: createParentId || undefined,
      });
      setPages((prev) => [...prev, created]);
      setShowCreateDialog(false);
      setCreateName("");
      setCreateType("board");
      setCreateParentId("");
      router.push(`/models/${modelId}/apps/${created.id}`);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create page");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeletePage(pageId: string) {
    try {
      await deleteUXPage(pageId);
      setPages((prev) => prev.filter((page) => page.id !== pageId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete page");
    }
  }

  function renderTree(parentId: string | null, depth: number) {
    const key = parentId ?? "__root__";
    const nodes = pagesByParent.get(key) ?? [];
    if (nodes.length === 0) {
      return null;
    }

    return (
      <div className={depth === 0 ? "space-y-3" : "space-y-2 border-l border-zinc-200 pl-4"}>
        {nodes.map((page) => (
          <div key={page.id} className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-zinc-900">{page.name}</span>
                  <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-600">
                    {page.page_type}
                  </span>
                  {page.is_published && (
                    <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-medium text-green-700">
                      Published
                    </span>
                  )}
                </div>
                {page.description && (
                  <p className="mt-1 text-xs text-zinc-500">{page.description}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Link
                  href={`/models/${modelId}/apps/${page.id}`}
                  className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-700"
                >
                  Open
                </Link>
                <button
                  type="button"
                  onClick={() => handleDeletePage(page.id)}
                  className="rounded-md border border-zinc-300 px-2 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
                >
                  Delete
                </button>
              </div>
            </div>
            {renderTree(page.id, depth + 1)}
          </div>
        ))}
      </div>
    );
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

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-800">
            App Navigation Tree
            {pages.length > 0 && (
              <span className="ml-2 text-sm font-normal text-zinc-500">
                ({pages.length})
              </span>
            )}
          </h2>
          <p className="mt-1 text-xs text-zinc-500">
            Create nested board, worksheet, and report pages for your UX app.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreateDialog(true)}
          className="w-full rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 sm:w-auto"
        >
          New App Page
        </button>
      </div>

      {pages.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-12 text-center">
          <p className="text-sm font-medium text-zinc-600">No UX pages yet</p>
          <p className="mt-1 text-xs text-zinc-500">
            Create your first page to start building the app experience.
          </p>
          <button
            type="button"
            onClick={() => setShowCreateDialog(true)}
            className="mt-4 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700"
          >
            Create First Page
          </button>
        </div>
      ) : (
        renderTree(null, 0)
      )}

      {showCreateDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-base font-semibold text-zinc-900">New App Page</h3>
            <p className="mt-1 text-xs text-zinc-500">
              Add a page to the app navigation tree.
            </p>

            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Page name
                </label>
                <input
                  type="text"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  placeholder="e.g. Product Analysis"
                  autoFocus
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Page type
                </label>
                <select
                  value={createType}
                  onChange={(e) => setCreateType(e.target.value as UXPageType)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="board">Board</option>
                  <option value="worksheet">Worksheet</option>
                  <option value="report">Report</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-700">
                  Parent page (optional)
                </label>
                <select
                  value={createParentId}
                  onChange={(e) => setCreateParentId(e.target.value)}
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                >
                  <option value="">Top-level page</option>
                  {pages.map((page) => (
                    <option key={page.id} value={page.id}>
                      {page.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {createError && (
              <p className="mt-3 text-xs text-red-600">{createError}</p>
            )}

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowCreateDialog(false);
                  setCreateError(null);
                }}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isCreating || !createName.trim()}
                onClick={handleCreatePage}
                className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-700 disabled:opacity-50"
              >
                {isCreating ? "Creating..." : "Create Page"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
