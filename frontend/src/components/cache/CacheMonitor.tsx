"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CacheStats {
  total_entries: number;
  valid_count: number;
  invalid_count: number;
  oldest_entry: string | null;
  newest_entry: string | null;
}

interface RecalcResult {
  entries_recalculated: number;
  entries_remaining: number;
}

interface CacheMonitorProps {
  modelId: string;
  token: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "short",
      timeStyle: "medium",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function buildUrl(modelId: string, path: string): string {
  return `/models/${modelId}/cache${path}`;
}

// ---------------------------------------------------------------------------
// Pie chart: valid vs invalid (SVG)
// ---------------------------------------------------------------------------

function CachePieChart({ valid, invalid }: { valid: number; invalid: number }) {
  const total = valid + invalid;
  if (total === 0) {
    return (
      <div className="flex items-center justify-center w-40 h-40 rounded-full border-4 border-zinc-200 bg-zinc-50">
        <span className="text-xs text-zinc-400">No data</span>
      </div>
    );
  }

  const validFraction = valid / total;
  const invalidFraction = invalid / total;

  // SVG pie via stroke-dasharray trick on a circle (r=15.9, circumference ~100)
  const r = 15.9155;
  const circumference = 2 * Math.PI * r; // ~100

  const validDash = validFraction * circumference;
  const invalidDash = invalidFraction * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 42 42" className="w-40 h-40" aria-label="Cache pie chart">
        {/* Background circle */}
        <circle cx="21" cy="21" r={r} fill="transparent" stroke="#e4e4e7" strokeWidth="3" />
        {/* Invalid segment (red) — drawn first (starts at 12 o'clock) */}
        {invalidFraction > 0 && (
          <circle
            cx="21"
            cy="21"
            r={r}
            fill="transparent"
            stroke="#ef4444"
            strokeWidth="3"
            strokeDasharray={`${invalidDash} ${circumference - invalidDash}`}
            strokeDashoffset={circumference * 0.25}
            transform="rotate(-90 21 21)"
          />
        )}
        {/* Valid segment (green) — offset past invalid */}
        {validFraction > 0 && (
          <circle
            cx="21"
            cy="21"
            r={r}
            fill="transparent"
            stroke="#22c55e"
            strokeWidth="3"
            strokeDasharray={`${validDash} ${circumference - validDash}`}
            strokeDashoffset={circumference * 0.25 - invalidDash}
            transform="rotate(-90 21 21)"
          />
        )}
        {/* Center label */}
        <text
          x="21"
          y="21.5"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="5"
          fill="#71717a"
        >
          {total}
        </text>
        <text
          x="21"
          y="26"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="3.5"
          fill="#a1a1aa"
        >
          entries
        </text>
      </svg>

      {/* Legend */}
      <div className="flex gap-4 text-xs text-zinc-600">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full bg-green-500" />
          Valid ({valid})
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full bg-red-500" />
          Invalid ({invalid})
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: "green" | "red" | "default";
}) {
  const colorMap = {
    green: "text-green-600",
    red: "text-red-600",
    default: "text-zinc-800",
  };
  const color = colorMap[accent ?? "default"];

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      <span className="text-xs font-medium text-zinc-500">{label}</span>
      <span className={`text-2xl font-semibold ${color}`}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CacheMonitor({ modelId, token }: CacheMonitorProps) {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const headers = { Authorization: `Bearer ${token}` };

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(buildUrl(modelId, "/stats"), { headers });
      if (!resp.ok) {
        throw new Error(`Failed to fetch stats: ${resp.statusText}`);
      }
      const data: CacheStats = await resp.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId, token]);

  // Initial load + auto-refresh every 30 seconds
  useEffect(() => {
    fetchStats();
    autoRefreshRef.current = setInterval(fetchStats, 30_000);
    return () => {
      if (autoRefreshRef.current !== null) {
        clearInterval(autoRefreshRef.current);
      }
    };
  }, [fetchStats]);

  async function handleClearCache() {
    setConfirmClear(false);
    setActionMessage(null);
    try {
      const resp = await fetch(buildUrl(modelId, ""), {
        method: "DELETE",
        headers,
      });
      if (!resp.ok) {
        throw new Error(`Clear failed: ${resp.statusText}`);
      }
      setActionMessage("Cache cleared successfully.");
      await fetchStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function handleRecalculate() {
    setActionMessage(null);
    try {
      const resp = await fetch(buildUrl(modelId, "/recalculate"), {
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
      await fetchStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-800">Cache Monitor</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Auto-refresh: 30s</span>
          <button
            type="button"
            onClick={fetchStats}
            disabled={loading}
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
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

      {stats ? (
        <>
          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Total Entries" value={stats.total_entries} />
            <StatCard label="Valid" value={stats.valid_count} accent="green" />
            <StatCard label="Invalid (Stale)" value={stats.invalid_count} accent="red" />
            <StatCard
              label="Hit Rate Estimate"
              value={
                stats.total_entries > 0
                  ? `${Math.round((stats.valid_count / stats.total_entries) * 100)}%`
                  : "—"
              }
              accent="default"
            />
          </div>

          {/* Timestamps */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg border border-zinc-200 bg-white p-4">
              <p className="text-xs font-medium text-zinc-500">Oldest Entry</p>
              <p className="mt-1 text-sm text-zinc-800 font-mono">
                {formatTimestamp(stats.oldest_entry)}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-4">
              <p className="text-xs font-medium text-zinc-500">Newest Entry</p>
              <p className="mt-1 text-sm text-zinc-800 font-mono">
                {formatTimestamp(stats.newest_entry)}
              </p>
            </div>
          </div>

          {/* Pie chart */}
          <div className="flex justify-center rounded-lg border border-zinc-200 bg-white p-6">
            <CachePieChart valid={stats.valid_count} invalid={stats.invalid_count} />
          </div>
        </>
      ) : (
        !loading && (
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-8 text-center text-sm text-zinc-400">
            No cache data available.
          </div>
        )
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        {/* Recalculate stale */}
        <button
          type="button"
          onClick={handleRecalculate}
          disabled={loading}
          className="rounded bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
        >
          Recalculate Stale
        </button>

        {/* Clear cache — with confirmation */}
        {confirmClear ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-red-600 font-medium">Are you sure?</span>
            <button
              type="button"
              onClick={handleClearCache}
              className="rounded bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
            >
              Yes, Clear Cache
            </button>
            <button
              type="button"
              onClick={() => setConfirmClear(false)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmClear(true)}
            disabled={loading}
            className="rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
          >
            Clear Cache
          </button>
        )}
      </div>
    </div>
  );
}
