"use client";

import { useState, useEffect, useCallback } from "react";
import { getDashboard, updateDashboard } from "@/lib/api";
import type { DashboardWithWidgets } from "@/lib/api";
import DashboardCanvas from "@/components/dashboard/DashboardCanvas";
import AddWidgetPanel from "@/components/dashboard/AddWidgetPanel";

interface Props {
  modelId: string;
  dashboardId: string;
}

export default function DashboardViewClient({ modelId, dashboardId }: Props) {
  const [dashboard, setDashboard] = useState<DashboardWithWidgets | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [showAddWidget, setShowAddWidget] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getDashboard(dashboardId);
      setDashboard(data);
      setEditTitle(data.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setIsLoading(false);
    }
  }, [dashboardId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleTogglePublish() {
    if (!dashboard) return;
    setIsPublishing(true);
    try {
      const updated = await updateDashboard(dashboardId, {
        is_published: !dashboard.is_published,
      });
      setDashboard((prev) => prev ? { ...prev, is_published: updated.is_published } : prev);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update dashboard");
    } finally {
      setIsPublishing(false);
    }
  }

  async function handleSaveTitle() {
    if (!dashboard || !editTitle.trim()) return;
    try {
      const updated = await updateDashboard(dashboardId, { name: editTitle.trim() });
      setDashboard((prev) => prev ? { ...prev, name: updated.name } : prev);
      setIsEditingTitle(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename dashboard");
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-3 py-6 sm:px-4 sm:py-8 md:px-6">
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  if (!dashboard) return null;

  return (
    <div className="flex min-h-[calc(100svh-56px)] flex-col">
      {/* Toolbar */}
      <div className="flex flex-col gap-3 border-b border-zinc-200 bg-white px-3 py-3 sm:px-4 md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex min-w-0 flex-wrap items-center gap-2 sm:gap-3">
          {isEditingTitle ? (
            <div className="flex w-full flex-wrap items-center gap-2">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveTitle();
                  if (e.key === "Escape") setIsEditingTitle(false);
                }}
                className="w-full rounded-md border border-violet-300 px-2 py-1 text-sm font-semibold text-zinc-900 focus:outline-none focus:ring-1 focus:ring-violet-500 sm:w-auto"
                autoFocus
              />
              <button
                type="button"
                onClick={handleSaveTitle}
                className="rounded-md bg-violet-600 px-2 py-1 text-xs font-medium text-white hover:bg-violet-700 transition-colors"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsEditingTitle(false);
                  setEditTitle(dashboard.name);
                }}
                className="rounded-md border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setIsEditingTitle(true)}
              className="group flex min-w-0 items-center gap-2 text-left text-base font-semibold text-zinc-900 hover:text-zinc-700"
              title="Click to rename"
            >
              <span className="truncate">{dashboard.name}</span>
              <PencilIcon className="h-3.5 w-3.5 shrink-0 text-zinc-400 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100" />
            </button>
          )}

          {dashboard.is_published && (
            <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
              Published
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleTogglePublish}
            disabled={isPublishing}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-50 sm:text-sm ${
              dashboard.is_published
                ? "border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
                : "border border-green-300 bg-green-50 text-green-700 hover:bg-green-100"
            }`}
          >
            {isPublishing ? "..." : dashboard.is_published ? "Unpublish" : "Publish"}
          </button>

          {isEditMode && (
            <button
              type="button"
              onClick={() => setShowAddWidget(true)}
              className="flex items-center gap-2 rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-700 sm:text-sm"
            >
              <PlusIcon className="h-4 w-4" />
              Add Widget
            </button>
          )}

          <button
            type="button"
            onClick={() => setIsEditMode((v) => !v)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm ${
              isEditMode
                ? "bg-zinc-800 text-white hover:bg-zinc-700"
                : "border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
            }`}
          >
            {isEditMode ? "Done Editing" : "Edit Layout"}
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 overflow-auto bg-zinc-100 p-2 sm:p-4 md:p-6">
        <DashboardCanvas
          dashboard={dashboard}
          isEditMode={isEditMode}
          onDashboardChange={setDashboard}
        />
      </div>

      {/* Add widget panel */}
      {showAddWidget && (
        <AddWidgetPanel
          dashboardId={dashboardId}
          onClose={() => setShowAddWidget(false)}
          onWidgetAdded={(widget) => {
            setDashboard((prev) =>
              prev ? { ...prev, widgets: [...prev.widgets, widget] } : prev
            );
            setShowAddWidget(false);
          }}
        />
      )}
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

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
    </svg>
  );
}
