"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StaleEntry {
  id: string;
  line_item_id: string;
  dimension_key: string;
  computed_value: string | null;
  formula_hash: string | null;
  is_valid: boolean;
  computed_at: string;
  expires_at: string | null;
}

interface RecalcResult {
  entries_recalculated: number;
  entries_remaining: number;
}

interface StaleEntriesTableProps {
  modelId: string;
  token: string;
  pageSize?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function truncate(str: string | null, maxLen: number = 30): string {
  if (!str) return "—";
  return str.length > maxLen ? str.slice(0, maxLen) + "…" : str;
}

function buildStaleUrl(modelId: string, limit: number, offset: number): string {
  return `/models/${modelId}/cache/stale?limit=${limit}&offset=${offset}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StaleEntriesTable({
  modelId,
  token,
  pageSize = 20,
}: StaleEntriesTableProps) {
  const [entries, setEntries] = useState<StaleEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchEntries = useCallback(
    async (pageIndex: number) => {
      setLoading(true);
      setError(null);
      const offset = pageIndex * pageSize;
      try {
        const resp = await fetch(buildStaleUrl(modelId, pageSize, offset), { headers });
        if (!resp.ok) {
          throw new Error(`Failed to fetch stale entries: ${resp.statusText}`);
        }
        const data: StaleEntry[] = await resp.json();
        setEntries(data);
        setHasMore(data.length === pageSize);
        setSelected(new Set());
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [modelId, token, pageSize]
  );

  useEffect(() => {
    fetchEntries(page);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (selected.size === entries.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(entries.map((e) => e.id)));
    }
  }

  async function handleRecalculateSelected() {
    setActionMessage(null);
    setError(null);
    try {
      // Trigger a recalculate batch (no per-entry selection on the API yet —
      // uses batch_size to process the next batch of stale entries)
      const resp = await fetch(`/models/${modelId}/cache/recalculate`, {
        method: "POST",
        headers,
      });
      if (!resp.ok) {
        throw new Error(`Recalculate failed: ${resp.statusText}`);
      }
      const result: RecalcResult = await resp.json();
      setActionMessage(
        `Recalculated ${result.entries_recalculated} entries. ${result.entries_remaining} remaining.`
      );
      // Reload current page
      await fetchEntries(page);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  function handlePrevPage() {
    if (page > 0) setPage((p) => p - 1);
  }

  function handleNextPage() {
    if (hasMore) setPage((p) => p + 1);
  }

  const allSelected = entries.length > 0 && selected.size === entries.length;
  const someSelected = selected.size > 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-800">Stale Cache Entries</h2>
        <button
          type="button"
          onClick={() => fetchEntries(page)}
          disabled={loading}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Action message */}
      {actionMessage && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {actionMessage}
        </div>
      )}

      {/* Bulk action bar */}
      {someSelected && (
        <div className="flex items-center gap-3 rounded-lg border border-violet-200 bg-violet-50 px-4 py-2">
          <span className="text-sm text-violet-700 font-medium">
            {selected.size} selected
          </span>
          <button
            type="button"
            onClick={handleRecalculateSelected}
            className="rounded bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
          >
            Recalculate Selected
          </button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            className="rounded border border-violet-300 px-3 py-1.5 text-sm font-medium text-violet-700 hover:bg-violet-100 transition-colors"
          >
            Clear Selection
          </button>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="w-10 px-3 py-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  aria-label="Select all"
                  className="rounded border-zinc-300"
                />
              </th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Line Item ID</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Dimension Key</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Last Computed</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Cached Value</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Formula Hash</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-zinc-400">
                  No stale entries found.
                </td>
              </tr>
            )}
            {entries.map((entry) => (
              <tr
                key={entry.id}
                onClick={() => toggleSelect(entry.id)}
                className={`border-b border-zinc-100 cursor-pointer transition-colors ${
                  selected.has(entry.id) ? "bg-violet-50" : "hover:bg-zinc-50"
                }`}
              >
                <td className="w-10 px-3 py-3" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(entry.id)}
                    onChange={() => toggleSelect(entry.id)}
                    className="rounded border-zinc-300"
                  />
                </td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-500 max-w-[160px] truncate">
                  {truncate(entry.line_item_id, 20)}
                </td>
                <td className="px-4 py-3 text-xs text-zinc-700 max-w-[180px] truncate font-mono">
                  {entry.dimension_key || "—"}
                </td>
                <td className="px-4 py-3 text-xs text-zinc-500 whitespace-nowrap">
                  {formatTimestamp(entry.computed_at)}
                </td>
                <td className="px-4 py-3 text-xs text-zinc-600 max-w-[120px] truncate font-mono">
                  {entry.computed_value ?? "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-400 max-w-[100px] truncate">
                  {truncate(entry.formula_hash, 12)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-500">
          Page {page + 1} — {entries.length} {entries.length === 1 ? "entry" : "entries"}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handlePrevPage}
            disabled={page === 0 || loading}
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={handleNextPage}
            disabled={!hasMore || loading}
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
