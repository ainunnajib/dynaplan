"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

interface TimeRange {
  id: string;
  model_id: string;
  name: string;
  start_period: string;
  end_period: string;
  granularity: string;
  is_model_default: boolean;
  created_at: string;
  updated_at: string;
}

// ── Component ────────────────────────────────────────────────────────────────

interface ModuleTimeRangeSelectorProps {
  modelId: string;
  moduleId: string;
}

export default function ModuleTimeRangeSelector({
  modelId,
  moduleId,
}: ModuleTimeRangeSelectorProps) {
  const [timeRanges, setTimeRanges] = useState<TimeRange[]>([]);
  const [effectiveTimeRange, setEffectiveTimeRange] =
    useState<TimeRange | null>(null);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOverride, setIsOverride] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [ranges, effective] = await Promise.all([
        fetchApi<TimeRange[]>(`/models/${modelId}/time-ranges`),
        fetchApi<TimeRange | null>(
          `/modules/${moduleId}/effective-time-range`
        ),
      ]);
      setTimeRanges(ranges);
      setEffectiveTimeRange(effective);

      // Determine if there's a module-level override by checking if effective
      // differs from model default (or if module has an explicit assignment)
      if (effective) {
        const modelDefault = ranges.find((r) => r.is_model_default);
        if (modelDefault && modelDefault.id === effective.id) {
          setSelectedId("");
          setIsOverride(false);
        } else {
          setSelectedId(effective.id);
          setIsOverride(true);
        }
      } else {
        setSelectedId("");
        setIsOverride(false);
      }

      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load time range data"
      );
    } finally {
      setLoading(false);
    }
  }, [modelId, moduleId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleAssign() {
    if (!selectedId) return;
    setSaving(true);
    setError(null);
    try {
      await fetchApi(`/modules/${moduleId}/time-range`, {
        method: "POST",
        body: JSON.stringify({ time_range_id: selectedId }),
      });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign time range");
    } finally {
      setSaving(false);
    }
  }

  async function handleUnassign() {
    setSaving(true);
    setError(null);
    try {
      await fetchApi(`/modules/${moduleId}/time-range`, {
        method: "DELETE",
      });
      setSelectedId("");
      setIsOverride(false);
      await fetchData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to remove time range override"
      );
    } finally {
      setSaving(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="text-sm text-zinc-500 py-2">
        Loading time range settings...
      </div>
    );
  }

  const modelDefault = timeRanges.find((r) => r.is_model_default);

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 space-y-3">
      <h3 className="text-sm font-semibold text-zinc-800">
        Module Time Range
      </h3>

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Current effective time range */}
      <div className="rounded-md bg-zinc-50 px-3 py-2 text-sm">
        <span className="font-medium text-zinc-700">Effective: </span>
        {effectiveTimeRange ? (
          <span className="text-zinc-900">
            {effectiveTimeRange.name} ({effectiveTimeRange.start_period} to{" "}
            {effectiveTimeRange.end_period})
            {isOverride ? (
              <span className="ml-2 inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
                Override
              </span>
            ) : (
              <span className="ml-2 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                Model Default
              </span>
            )}
          </span>
        ) : (
          <span className="text-zinc-400">None (no model default set)</span>
        )}
      </div>

      {/* Assignment controls */}
      {timeRanges.length === 0 ? (
        <p className="text-xs text-zinc-500">
          No time ranges are defined for this model. Create time ranges in the
          model settings first.
        </p>
      ) : (
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label className="block text-xs font-medium text-zinc-600 mb-1">
              Override with
            </label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            >
              <option value="">
                Use model default
                {modelDefault ? ` (${modelDefault.name})` : ""}
              </option>
              {timeRanges.map((tr) => (
                <option key={tr.id} value={tr.id}>
                  {tr.name} ({tr.start_period} to {tr.end_period})
                </option>
              ))}
            </select>
          </div>

          {selectedId ? (
            <button
              onClick={handleAssign}
              disabled={saving}
              className="rounded-md bg-violet-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
              type="button"
            >
              {saving ? "Saving..." : "Apply Override"}
            </button>
          ) : isOverride ? (
            <button
              onClick={handleUnassign}
              disabled={saving}
              className="rounded-md border border-zinc-300 px-4 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
              type="button"
            >
              {saving ? "Removing..." : "Remove Override"}
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
