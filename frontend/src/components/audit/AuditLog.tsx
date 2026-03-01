"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AuditEventType =
  | "cell_update"
  | "cell_delete"
  | "line_item_create"
  | "line_item_update"
  | "line_item_delete"
  | "module_create"
  | "module_update"
  | "module_delete"
  | "dimension_create"
  | "dimension_update"
  | "dimension_delete"
  | "model_update";

interface AuditEntry {
  id: string;
  model_id: string;
  event_type: AuditEventType;
  entity_type: string;
  entity_id: string;
  user_id: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  metadata_: Record<string, unknown> | null;
  created_at: string;
}

interface AuditLogProps {
  modelId: string;
  token: string;
  pageSize?: number;
}

const ALL_EVENT_TYPES: AuditEventType[] = [
  "cell_update",
  "cell_delete",
  "line_item_create",
  "line_item_update",
  "line_item_delete",
  "module_create",
  "module_update",
  "module_delete",
  "dimension_create",
  "dimension_update",
  "dimension_delete",
  "model_update",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatEventType(et: string): string {
  return et.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatValue(value: Record<string, unknown> | null): string {
  if (value === null || value === undefined) return "—";
  return JSON.stringify(value);
}

function eventTypeBadgeColor(et: AuditEventType): string {
  if (et.endsWith("_delete")) return "bg-red-100 text-red-700";
  if (et.endsWith("_create")) return "bg-green-100 text-green-700";
  if (et.endsWith("_update")) return "bg-blue-100 text-blue-700";
  return "bg-zinc-100 text-zinc-700";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AuditLog({ modelId, token, pageSize = 20 }: AuditLogProps) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [filterEventType, setFilterEventType] = useState<AuditEventType | "">("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterUserId, setFilterUserId] = useState("");

  const buildUrl = useCallback(
    (currentOffset: number) => {
      const params = new URLSearchParams();
      params.set("limit", String(pageSize));
      params.set("offset", String(currentOffset));
      if (filterEventType) params.set("event_type", filterEventType);
      if (filterDateFrom) params.set("after", new Date(filterDateFrom).toISOString());
      if (filterDateTo) params.set("before", new Date(filterDateTo).toISOString());
      if (filterUserId.trim()) params.set("user_id", filterUserId.trim());
      return `/models/${modelId}/audit?${params.toString()}`;
    },
    [modelId, pageSize, filterEventType, filterDateFrom, filterDateTo, filterUserId]
  );

  const fetchEntries = useCallback(
    async (reset: boolean) => {
      setLoading(true);
      setError(null);
      const currentOffset = reset ? 0 : offset;
      try {
        const resp = await fetch(buildUrl(currentOffset), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!resp.ok) {
          throw new Error(`Failed to load audit log: ${resp.statusText}`);
        }
        const data: AuditEntry[] = await resp.json();
        setEntries((prev) => (reset ? data : [...prev, ...data]));
        setOffset(currentOffset + data.length);
        setHasMore(data.length === pageSize);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [buildUrl, offset, pageSize, token]
  );

  // Reload when filters change
  useEffect(() => {
    setOffset(0);
    setEntries([]);
    setHasMore(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterEventType, filterDateFrom, filterDateTo, filterUserId]);

  useEffect(() => {
    fetchEntries(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterEventType, filterDateFrom, filterDateTo, filterUserId]);

  function handleLoadMore() {
    fetchEntries(false);
  }

  function handleApplyFilters(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    setEntries([]);
    setHasMore(true);
    fetchEntries(true);
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Filter bar */}
      <form
        onSubmit={handleApplyFilters}
        className="flex flex-wrap items-end gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4"
      >
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-600">Event Type</label>
          <select
            value={filterEventType}
            onChange={(e) => setFilterEventType(e.target.value as AuditEventType | "")}
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-violet-300"
          >
            <option value="">All types</option>
            {ALL_EVENT_TYPES.map((et) => (
              <option key={et} value={et}>
                {formatEventType(et)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-600">From</label>
          <input
            type="datetime-local"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-violet-300"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-600">To</label>
          <input
            type="datetime-local"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-violet-300"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-600">User ID</label>
          <input
            type="text"
            value={filterUserId}
            onChange={(e) => setFilterUserId(e.target.value)}
            placeholder="UUID..."
            className="rounded border border-zinc-300 px-2 py-1.5 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-300"
          />
        </div>

        <button
          type="submit"
          className="rounded bg-violet-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
        >
          Apply
        </button>

        <button
          type="button"
          onClick={() => {
            setFilterEventType("");
            setFilterDateFrom("");
            setFilterDateTo("");
            setFilterUserId("");
          }}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-100 transition-colors"
        >
          Clear
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-zinc-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50">
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Timestamp</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">User</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Event</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Entity</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">Old Value</th>
              <th className="px-4 py-3 text-left font-medium text-zinc-600">New Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-zinc-400">
                  No audit entries found.
                </td>
              </tr>
            )}
            {entries.map((entry) => (
              <tr
                key={entry.id}
                className="border-b border-zinc-100 hover:bg-zinc-50 transition-colors"
              >
                <td className="px-4 py-3 font-mono text-xs text-zinc-500 whitespace-nowrap">
                  {formatTimestamp(entry.created_at)}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-zinc-500 max-w-[120px] truncate">
                  {entry.user_id ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${eventTypeBadgeColor(entry.event_type)}`}
                  >
                    {formatEventType(entry.event_type)}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-zinc-700">
                  <span className="font-medium">{entry.entity_type}</span>
                  <span className="ml-1 font-mono text-zinc-400 text-xs truncate max-w-[100px] inline-block align-middle">
                    {entry.entity_id}
                  </span>
                </td>
                <td className="px-4 py-3 max-w-[200px] truncate font-mono text-xs text-zinc-500">
                  {formatValue(entry.old_value)}
                </td>
                <td className="px-4 py-3 max-w-[200px] truncate font-mono text-xs text-zinc-500">
                  {formatValue(entry.new_value)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Load more */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-zinc-500">
          Showing {entries.length} {entries.length === 1 ? "entry" : "entries"}
        </span>
        {hasMore && (
          <button
            type="button"
            onClick={handleLoadMore}
            disabled={loading}
            className="rounded border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            {loading ? "Loading..." : "Load more"}
          </button>
        )}
      </div>
    </div>
  );
}
