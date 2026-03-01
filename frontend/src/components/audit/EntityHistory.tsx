"use client";

import { useEffect, useState } from "react";

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

interface EntityHistoryProps {
  entityType: string;
  entityId: string;
  token: string;
  limit?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatEventType(et: string): string {
  return et.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function eventTypeColor(et: AuditEventType): string {
  if (et.endsWith("_delete")) return "border-red-400 bg-red-50";
  if (et.endsWith("_create")) return "border-green-400 bg-green-50";
  if (et.endsWith("_update")) return "border-blue-400 bg-blue-50";
  return "border-zinc-300 bg-zinc-50";
}

function eventTypeDotColor(et: AuditEventType): string {
  if (et.endsWith("_delete")) return "bg-red-400";
  if (et.endsWith("_create")) return "bg-green-400";
  if (et.endsWith("_update")) return "bg-blue-400";
  return "bg-zinc-400";
}

// ---------------------------------------------------------------------------
// Diff view sub-component
// ---------------------------------------------------------------------------

interface DiffProps {
  oldValue: Record<string, unknown> | null;
  newValue: Record<string, unknown> | null;
  expanded: boolean;
}

function ValueDiff({ oldValue, newValue, expanded }: DiffProps) {
  if (!expanded) return null;

  const allKeys = new Set<string>([
    ...Object.keys(oldValue ?? {}),
    ...Object.keys(newValue ?? {}),
  ]);

  if (allKeys.size === 0) {
    return (
      <p className="mt-2 text-xs text-zinc-400 italic">No value details available.</p>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto rounded border border-zinc-200 bg-white">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-100 bg-zinc-50">
            <th className="px-3 py-2 text-left font-medium text-zinc-500">Field</th>
            <th className="px-3 py-2 text-left font-medium text-red-500">Old</th>
            <th className="px-3 py-2 text-left font-medium text-green-600">New</th>
          </tr>
        </thead>
        <tbody>
          {[...allKeys].map((key) => {
            const oldVal = oldValue ? oldValue[key] : undefined;
            const newVal = newValue ? newValue[key] : undefined;
            const changed =
              JSON.stringify(oldVal) !== JSON.stringify(newVal);
            return (
              <tr
                key={key}
                className={[
                  "border-b border-zinc-50",
                  changed ? "bg-yellow-50" : "",
                ].join(" ")}
              >
                <td className="px-3 py-1.5 font-medium text-zinc-600">{key}</td>
                <td className="px-3 py-1.5 font-mono text-red-600">
                  {oldVal !== undefined ? JSON.stringify(oldVal) : <span className="text-zinc-300">—</span>}
                </td>
                <td className="px-3 py-1.5 font-mono text-green-700">
                  {newVal !== undefined ? JSON.stringify(newVal) : <span className="text-zinc-300">—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Timeline item
// ---------------------------------------------------------------------------

interface TimelineItemProps {
  entry: AuditEntry;
  isLast: boolean;
}

function TimelineItem({ entry, isLast }: TimelineItemProps) {
  const [expanded, setExpanded] = useState(false);
  const hasDiff = entry.old_value !== null || entry.new_value !== null;

  return (
    <div className="flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={`mt-1 h-3 w-3 flex-shrink-0 rounded-full border-2 border-white shadow ${eventTypeDotColor(entry.event_type)}`}
        />
        {!isLast && <div className="mt-1 w-0.5 flex-1 bg-zinc-200" />}
      </div>

      {/* Content card */}
      <div
        className={`mb-4 flex-1 rounded-lg border-l-4 p-4 shadow-sm ${eventTypeColor(entry.event_type)}`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-semibold text-zinc-800">
              {formatEventType(entry.event_type)}
            </span>
            <span className="text-xs text-zinc-500">
              {formatTimestamp(entry.created_at)}
            </span>
            {entry.user_id && (
              <span className="font-mono text-xs text-zinc-400">
                by {entry.user_id}
              </span>
            )}
          </div>

          {hasDiff && (
            <button
              type="button"
              onClick={() => setExpanded((prev) => !prev)}
              className="flex-shrink-0 rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-600 hover:bg-white transition-colors"
            >
              {expanded ? "Hide diff" : "Show diff"}
            </button>
          )}
        </div>

        {/* Metadata badges */}
        {entry.metadata_ && Object.keys(entry.metadata_).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {Object.entries(entry.metadata_).map(([k, v]) => (
              <span
                key={k}
                className="inline-block rounded-full bg-white/70 border border-zinc-200 px-2 py-0.5 text-xs text-zinc-500"
              >
                {k}: {JSON.stringify(v)}
              </span>
            ))}
          </div>
        )}

        <ValueDiff
          oldValue={entry.old_value}
          newValue={entry.new_value}
          expanded={expanded}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function EntityHistory({
  entityType,
  entityId,
  token,
  limit = 20,
}: EntityHistoryProps) {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams({ limit: String(limit) });
        const resp = await fetch(
          `/audit/entity/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}?${params.toString()}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!resp.ok) {
          throw new Error(`Failed to load history: ${resp.statusText}`);
        }
        const data: AuditEntry[] = await resp.json();
        setEntries(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [entityType, entityId, token, limit]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-zinc-400">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-violet-500" />
        Loading history...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-zinc-800">
            Change History
          </h3>
          <p className="mt-0.5 text-xs text-zinc-500">
            <span className="font-medium">{entityType}</span>
            {" / "}
            <span className="font-mono">{entityId}</span>
          </p>
        </div>
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600">
          {entries.length} {entries.length === 1 ? "event" : "events"}
        </span>
      </div>

      {/* Timeline */}
      {entries.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-400">
          No history found for this entity.
        </p>
      ) : (
        <div className="relative pl-1">
          {entries.map((entry, idx) => (
            <TimelineItem
              key={entry.id}
              entry={entry}
              isLast={idx === entries.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
