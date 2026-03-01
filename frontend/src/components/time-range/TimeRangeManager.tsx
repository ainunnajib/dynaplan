"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type Granularity = "month" | "quarter" | "year";

interface TimeRange {
  id: string;
  model_id: string;
  name: string;
  start_period: string;
  end_period: string;
  granularity: Granularity;
  is_model_default: boolean;
  created_at: string;
  updated_at: string;
}

interface TimeRangeFormData {
  name: string;
  start_period: string;
  end_period: string;
  granularity: Granularity;
  is_model_default: boolean;
}

const EMPTY_FORM: TimeRangeFormData = {
  name: "",
  start_period: "",
  end_period: "",
  granularity: "month",
  is_model_default: false,
};

// ── Component ────────────────────────────────────────────────────────────────

interface TimeRangeManagerProps {
  modelId: string;
}

export default function TimeRangeManager({ modelId }: TimeRangeManagerProps) {
  const [timeRanges, setTimeRanges] = useState<TimeRange[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<TimeRangeFormData>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Delete state
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchTimeRanges = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchApi<TimeRange[]>(
        `/models/${modelId}/time-ranges`
      );
      setTimeRanges(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load time ranges");
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    fetchTimeRanges();
  }, [fetchTimeRanges]);

  function openCreateForm() {
    setFormData(EMPTY_FORM);
    setEditingId(null);
    setFormError(null);
    setShowForm(true);
  }

  function openEditForm(tr: TimeRange) {
    setFormData({
      name: tr.name,
      start_period: tr.start_period,
      end_period: tr.end_period,
      granularity: tr.granularity,
      is_model_default: tr.is_model_default,
    });
    setEditingId(tr.id);
    setFormError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
    setFormError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);

    try {
      if (editingId) {
        await fetchApi(`/time-ranges/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(formData),
        });
      } else {
        await fetchApi(`/models/${modelId}/time-ranges`, {
          method: "POST",
          body: JSON.stringify(formData),
        });
      }
      closeForm();
      await fetchTimeRanges();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await fetchApi(`/time-ranges/${id}`, { method: "DELETE" });
      await fetchTimeRanges();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  function placeholderForGranularity(granularity: Granularity): string {
    switch (granularity) {
      case "month":
        return "YYYY-MM";
      case "quarter":
        return "YYYY-QN";
      case "year":
        return "YYYY";
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-zinc-500">
        Loading time ranges...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-900">Time Ranges</h2>
        <button
          onClick={openCreateForm}
          className="rounded-md bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
          type="button"
        >
          + New Time Range
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-zinc-200 bg-white p-4 space-y-3 shadow-sm"
        >
          <h3 className="text-sm font-semibold text-zinc-800">
            {editingId ? "Edit Time Range" : "Create Time Range"}
          </h3>

          {formError && (
            <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                Name
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
                className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder="e.g. FY2024"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                Granularity
              </label>
              <select
                value={formData.granularity}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    granularity: e.target.value as Granularity,
                  })
                }
                className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              >
                <option value="month">Month</option>
                <option value="quarter">Quarter</option>
                <option value="year">Year</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                Start Period
              </label>
              <input
                type="text"
                value={formData.start_period}
                onChange={(e) =>
                  setFormData({ ...formData, start_period: e.target.value })
                }
                required
                className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder={placeholderForGranularity(formData.granularity)}
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1">
                End Period
              </label>
              <input
                type="text"
                value={formData.end_period}
                onChange={(e) =>
                  setFormData({ ...formData, end_period: e.target.value })
                }
                required
                className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder={placeholderForGranularity(formData.granularity)}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-zinc-700">
            <input
              type="checkbox"
              checked={formData.is_model_default}
              onChange={(e) =>
                setFormData({ ...formData, is_model_default: e.target.checked })
              }
              className="rounded border-zinc-300 text-violet-600 focus:ring-violet-500"
            />
            Set as model default
          </label>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-violet-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Saving..." : editingId ? "Update" : "Create"}
            </button>
            <button
              type="button"
              onClick={closeForm}
              disabled={submitting}
              className="rounded-md border border-zinc-300 px-4 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Table */}
      {timeRanges.length === 0 && !showForm ? (
        <div className="rounded-lg border border-dashed border-zinc-300 py-8 text-center text-sm text-zinc-500">
          No time ranges defined yet. Create one to set planning horizons.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-200">
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-zinc-600">
                  Name
                </th>
                <th className="px-4 py-2 text-left font-medium text-zinc-600">
                  Period
                </th>
                <th className="px-4 py-2 text-left font-medium text-zinc-600">
                  Granularity
                </th>
                <th className="px-4 py-2 text-left font-medium text-zinc-600">
                  Default
                </th>
                <th className="px-4 py-2 text-right font-medium text-zinc-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {timeRanges.map((tr) => (
                <tr key={tr.id} className="hover:bg-zinc-50 transition-colors">
                  <td className="px-4 py-2 font-medium text-zinc-900">
                    {tr.name}
                  </td>
                  <td className="px-4 py-2 text-zinc-600">
                    {tr.start_period} to {tr.end_period}
                  </td>
                  <td className="px-4 py-2 text-zinc-600 capitalize">
                    {tr.granularity}
                  </td>
                  <td className="px-4 py-2">
                    {tr.is_model_default ? (
                      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                        Default
                      </span>
                    ) : (
                      <span className="text-zinc-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEditForm(tr)}
                        className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors"
                        title="Edit"
                        type="button"
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(tr.id)}
                        disabled={deletingId === tr.id}
                        className="rounded p-1 text-zinc-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 transition-colors"
                        title="Delete"
                        type="button"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Icons ────────────────────────────────────────────────────────────────────

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125"
      />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
      />
    </svg>
  );
}
