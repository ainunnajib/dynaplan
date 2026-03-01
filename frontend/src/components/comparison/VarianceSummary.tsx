"use client";

import { useCallback, useState } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface VarianceSummaryData {
  total_absolute_diff: number;
  avg_percentage_diff: number | null;
  changed_cells: number;
  unchanged_cells: number;
  total_cells: number;
}

interface VarianceSummaryProps {
  modelId: string;
  availableVersions: Version[];
}

// ── KPI Card ──────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  subtext?: string;
  highlight?: "positive" | "negative" | "neutral";
}

function KpiCard({ label, value, subtext, highlight }: KpiCardProps) {
  const valueColor =
    highlight === "positive"
      ? "text-green-600"
      : highlight === "negative"
      ? "text-red-600"
      : "text-gray-800";

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</span>
      <span className={`text-2xl font-bold tabular-nums ${valueColor}`}>{value}</span>
      {subtext && <span className="text-xs text-gray-400">{subtext}</span>}
    </div>
  );
}

// ── Mini bar chart ─────────────────────────────────────────────────────────────

interface MiniBarChartProps {
  changed: number;
  unchanged: number;
  total: number;
}

function MiniBarChart({ changed, unchanged, total }: MiniBarChartProps) {
  if (total === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
          Changed vs Unchanged
        </span>
        <p className="mt-2 text-sm text-gray-400">No cells to display</p>
      </div>
    );
  }

  const changedPct = (changed / total) * 100;
  const unchangedPct = (unchanged / total) * 100;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
        Changed vs Unchanged Cells
      </span>

      {/* Stacked bar */}
      <div className="flex h-6 w-full overflow-hidden rounded-full bg-gray-100">
        {changedPct > 0 && (
          <div
            className="flex items-center justify-center bg-amber-400 text-[10px] font-medium text-white"
            style={{ width: `${changedPct}%` }}
          >
            {changedPct > 15 ? `${changed}` : ""}
          </div>
        )}
        {unchangedPct > 0 && (
          <div
            className="flex items-center justify-center bg-green-400 text-[10px] font-medium text-white"
            style={{ width: `${unchangedPct}%` }}
          >
            {unchangedPct > 15 ? `${unchanged}` : ""}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-gray-600">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-amber-400" />
          Changed: {changed}
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-green-400" />
          Unchanged: {unchanged}
        </span>
      </div>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function VarianceSummary({ modelId, availableVersions }: VarianceSummaryProps) {
  const [baseVersionId, setBaseVersionId] = useState<string>("");
  const [compareVersionId, setCompareVersionId] = useState<string>("");
  const [summaryData, setSummaryData] = useState<VarianceSummaryData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    if (!baseVersionId || !compareVersionId) {
      setError("Please select both a base and compare version.");
      return;
    }
    if (baseVersionId === compareVersionId) {
      setError("Base and compare versions must be different.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<VarianceSummaryData>(
        `/models/${modelId}/compare/variance`,
        {
          method: "POST",
          body: JSON.stringify({
            base_version_id: baseVersionId,
            compare_version_id: compareVersionId,
          }),
        }
      );
      setSummaryData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch variance summary");
    } finally {
      setIsLoading(false);
    }
  }, [modelId, baseVersionId, compareVersionId]);

  const formatAbsDiff = (v: number) =>
    v.toLocaleString(undefined, { maximumFractionDigits: 2 });

  const formatPctDiff = (v: number | null) =>
    v === null ? "N/A" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

  return (
    <div className="flex flex-col gap-4">
      {/* Version pickers */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Variance Analysis</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500">Base Version</label>
            <select
              value={baseVersionId}
              onChange={(e) => {
                setBaseVersionId(e.target.value);
                setSummaryData(null);
              }}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select base version...</option>
              {availableVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.version_type})
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500">Compare Version</label>
            <select
              value={compareVersionId}
              onChange={(e) => {
                setCompareVersionId(e.target.value);
                setSummaryData(null);
              }}
              className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select compare version...</option>
              {availableVersions
                .filter((v) => v.id !== baseVersionId)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.version_type})
                  </option>
                ))}
            </select>
          </div>

          <button
            onClick={handleFetch}
            disabled={!baseVersionId || !compareVersionId || isLoading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
          >
            {isLoading ? "Loading..." : "Analyze"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* KPI Cards */}
      {summaryData && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiCard
              label="Total Absolute Diff"
              value={formatAbsDiff(summaryData.total_absolute_diff)}
              subtext="Sum of all cell differences"
              highlight={summaryData.total_absolute_diff > 0 ? "negative" : "positive"}
            />
            <KpiCard
              label="Avg % Difference"
              value={formatPctDiff(summaryData.avg_percentage_diff)}
              subtext={summaryData.avg_percentage_diff === null ? "Base values are zero" : "Average across changed cells"}
              highlight={
                summaryData.avg_percentage_diff === null
                  ? "neutral"
                  : summaryData.avg_percentage_diff >= 0
                  ? "positive"
                  : "negative"
              }
            />
            <KpiCard
              label="Changed Cells"
              value={String(summaryData.changed_cells)}
              subtext={`of ${summaryData.total_cells} total`}
              highlight={summaryData.changed_cells > 0 ? "negative" : "positive"}
            />
            <KpiCard
              label="Unchanged Cells"
              value={String(summaryData.unchanged_cells)}
              subtext={`of ${summaryData.total_cells} total`}
              highlight="neutral"
            />
          </div>

          {/* Mini bar chart */}
          <MiniBarChart
            changed={summaryData.changed_cells}
            unchanged={summaryData.unchanged_cells}
            total={summaryData.total_cells}
          />
        </>
      )}
    </div>
  );
}
