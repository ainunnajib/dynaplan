"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_SAVED_VIEW_CONFIG,
  createSavedView,
  deleteSavedView,
  getSavedViews,
  setSavedViewDefault,
  type SavedView,
  type SavedViewConfig,
  updateSavedView,
} from "@/lib/api";

interface SavedViewToolbarProps {
  moduleId: string;
  currentViewConfig: SavedViewConfig;
  onApplyViewConfig: (viewConfig: SavedViewConfig) => void;
}

function normalizeConfig(viewConfig: SavedViewConfig | undefined): SavedViewConfig {
  if (!viewConfig) return DEFAULT_SAVED_VIEW_CONFIG;
  return {
    row_dims: viewConfig.row_dims ?? [],
    col_dims: viewConfig.col_dims ?? [],
    filters: viewConfig.filters ?? {},
    sort: {
      column_key: viewConfig.sort?.column_key ?? null,
      direction: viewConfig.sort?.direction ?? "asc",
    },
  };
}

export default function SavedViewToolbar({
  moduleId,
  currentViewConfig,
  onApplyViewConfig,
}: SavedViewToolbarProps) {
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [selectedViewId, setSelectedViewId] = useState<string | null>(null);
  const [viewName, setViewName] = useState("");
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const defaultAppliedRef = useRef(false);

  const loadSavedViews = useCallback(
    async (applyDefault: boolean) => {
      setIsLoading(true);
      setError(null);
      try {
        const views = await getSavedViews(moduleId);
        setSavedViews(views);

        if (applyDefault && !defaultAppliedRef.current) {
          const defaultView = views.find((view) => view.is_default);
          if (defaultView) {
            defaultAppliedRef.current = true;
            setSelectedViewId(defaultView.id);
            setViewName(defaultView.name);
            onApplyViewConfig(normalizeConfig(defaultView.view_config));
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load saved views");
      } finally {
        setIsLoading(false);
      }
    },
    [moduleId, onApplyViewConfig]
  );

  useEffect(() => {
    defaultAppliedRef.current = false;
    setSelectedViewId(null);
    setViewName("");
    setSaveAsDefault(false);
    void loadSavedViews(true);
  }, [loadSavedViews, moduleId]);

  useEffect(() => {
    if (!selectedViewId) return;
    const selected = savedViews.find((view) => view.id === selectedViewId);
    if (!selected) return;
    setViewName(selected.name);
  }, [savedViews, selectedViewId]);

  async function handleCreateView() {
    if (!viewName.trim()) {
      setError("Saved view name is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createSavedView(moduleId, {
        name: viewName.trim(),
        view_config: currentViewConfig,
        is_default: saveAsDefault,
      });
      setSelectedViewId(created.id);
      setViewName(created.name);
      setSaveAsDefault(false);
      await loadSavedViews(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save view");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateView() {
    if (!selectedViewId) return;
    if (!viewName.trim()) {
      setError("Saved view name is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const updated = await updateSavedView(selectedViewId, {
        name: viewName.trim(),
        view_config: currentViewConfig,
      });
      setViewName(updated.name);
      await loadSavedViews(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update view");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSetDefault() {
    if (!selectedViewId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await setSavedViewDefault(selectedViewId);
      await loadSavedViews(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set default view");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeleteView() {
    if (!selectedViewId) return;
    if (!confirm("Delete this saved view?")) return;

    setIsSubmitting(true);
    setError(null);
    try {
      await deleteSavedView(selectedViewId);
      setSelectedViewId(null);
      setViewName("");
      await loadSavedViews(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete saved view");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSelectView(nextId: string) {
    if (!nextId) {
      setSelectedViewId(null);
      setViewName("");
      return;
    }
    const selected = savedViews.find((view) => view.id === nextId);
    if (!selected) return;
    setSelectedViewId(selected.id);
    setViewName(selected.name);
    onApplyViewConfig(normalizeConfig(selected.view_config));
  }

  const selectedView =
    savedViews.find((view) => view.id === selectedViewId) ?? null;

  return (
    <div className="rounded-md border border-zinc-200 bg-white px-3 py-2 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <label
          htmlFor="saved-view-selector"
          className="text-xs font-semibold uppercase tracking-wide text-zinc-500"
        >
          Saved View
        </label>
        <select
          id="saved-view-selector"
          value={selectedViewId ?? ""}
          onChange={(event) => handleSelectView(event.target.value)}
          className="h-9 min-w-[180px] rounded border border-zinc-300 bg-white px-2 text-sm text-zinc-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          disabled={isLoading || isSubmitting}
        >
          <option value="">Current (unsaved)</option>
          {savedViews.map((view) => (
            <option key={view.id} value={view.id}>
              {view.name}
              {view.is_default ? " (default)" : ""}
            </option>
          ))}
        </select>

        <input
          type="text"
          value={viewName}
          onChange={(event) => setViewName(event.target.value)}
          placeholder="View name"
          className="h-9 min-w-[180px] rounded border border-zinc-300 px-2 text-sm text-zinc-700 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          disabled={isSubmitting}
        />

        <button
          type="button"
          onClick={handleCreateView}
          className="h-9 rounded bg-blue-600 px-3 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting || isLoading}
        >
          Save New
        </button>

        <button
          type="button"
          onClick={handleUpdateView}
          className="h-9 rounded border border-zinc-300 px-3 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting || !selectedViewId}
        >
          Update
        </button>

        <button
          type="button"
          onClick={handleSetDefault}
          className="h-9 rounded border border-amber-300 bg-amber-50 px-3 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting || !selectedViewId}
        >
          Set Default
        </button>

        <button
          type="button"
          onClick={handleDeleteView}
          className="h-9 rounded border border-red-300 bg-red-50 px-3 text-sm font-medium text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isSubmitting || !selectedViewId}
        >
          Delete
        </button>

        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-600">
          <input
            type="checkbox"
            checked={saveAsDefault}
            onChange={(event) => setSaveAsDefault(event.target.checked)}
            disabled={isSubmitting}
            className="h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
          />
          Save as default
        </label>
      </div>

      {isLoading && (
        <p className="mt-2 text-xs text-zinc-500">Loading saved views...</p>
      )}

      {!isLoading && selectedView && (
        <p className="mt-2 text-xs text-zinc-500">
          Active: <span className="font-medium text-zinc-700">{selectedView.name}</span>
          {selectedView.is_default ? " (default)" : ""}
        </p>
      )}

      {error && (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  );
}
