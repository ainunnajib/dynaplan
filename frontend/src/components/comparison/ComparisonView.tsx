"use client";

import { useCallback, useMemo, useState } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface ComparisonRow {
  line_item_id: string;
  line_item_name: string;
  dimension_key: string;
  values: Record<string, number | null>;
  absolute_diff: number | null;
  percentage_diff: number | null;
}

interface ComparisonResponse {
  rows: ComparisonRow[];
  version_names: Record<string, string>;
}

interface ComparisonViewProps {
  modelId: string;
  availableVersions: Version[];
}

type SortKey = "line_item_name" | "dimension_key" | "absolute_diff" | "percentage_diff" | string;
type SortDir = "asc" | "desc";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDiff(value: number | null, isPercent: boolean): string {
  if (value === null) return "—";
  const sign = value > 0 ? "+" : "";
  if (isPercent) {
    return `${sign}${value.toFixed(1)}%`;
  }
  return `${sign}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function diffColor(value: number | null): string {
  if (value === null) return "text-gray-400";
  if (value > 0) return "text-green-600 font-medium";
  if (value < 0) return "text-red-600 font-medium";
  return "text-gray-500";
}

function formatValue(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ComparisonView({ modelId, availableVersions }: ComparisonViewProps) {
  const [selectedVersionIds, setSelectedVersionIds] = useState<string[]>([]);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("line_item_name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Handle version selector checkboxes (allow 2-4 versions)
  const handleVersionToggle = useCallback((versionId: string) => {
    setSelectedVersionIds((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 4) {
        return prev; // max 4 versions
      }
      return [...prev, versionId];
    });
    // Reset comparison data when selection changes
    setComparisonData(null);
    setError(null);
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedVersionIds.length < 2) {
      setError("Please select at least 2 versions to compare.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<ComparisonResponse>(`/models/${modelId}/compare`, {
        method: "POST",
        body: JSON.stringify({ version_ids: selectedVersionIds }),
      });
      setComparisonData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setIsLoading(false);
    }
  }, [modelId, selectedVersionIds]);

  // Sort rows
  const sortedRows = useMemo(() => {
    if (!comparisonData) return [];
    return [...comparisonData.rows].sort((a, b) => {
      let valA: number | string | null = null;
      let valB: number | string | null = null;

      if (sortKey === "line_item_name") {
        valA = a.line_item_name;
        valB = b.line_item_name;
      } else if (sortKey === "dimension_key") {
        valA = a.dimension_key;
        valB = b.dimension_key;
      } else if (sortKey === "absolute_diff") {
        valA = a.absolute_diff;
        valB = b.absolute_diff;
      } else if (sortKey === "percentage_diff") {
        valA = a.percentage_diff;
        valB = b.percentage_diff;
      } else {
        // It's a version_id key
        valA = a.values[sortKey] ?? null;
        valB = b.values[sortKey] ?? null;
      }

      if (valA === null && valB === null) return 0;
      if (valA === null) return 1;
      if (valB === null) return -1;

      const cmp =
        typeof valA === "string" && typeof valB === "string"
          ? valA.localeCompare(valB)
          : (valA as number) - (valB as number);

      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [comparisonData, sortKey, sortDir]);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey]
  );

  const SortIcon = ({ colKey }: { colKey: SortKey }) => {
    if (sortKey !== colKey) {
      return <span className="ml-1 text-gray-300">&#8597;</span>;
    }
    return (
      <span className="ml-1 text-blue-500">
        {sortDir === "asc" ? "\u2191" : "\u2193"}
      </span>
    );
  };

  const versionIds = comparisonData ? selectedVersionIds : [];

  return (
    <div className="flex flex-col gap-4">
      {/* Version selector */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">
          Select Versions to Compare (2 to 4)
        </h2>
        <div className="flex flex-wrap gap-3">
          {availableVersions.map((v) => {
            const isSelected = selectedVersionIds.includes(v.id);
            const isDisabled = !isSelected && selectedVersionIds.length >= 4;
            return (
              <label
                key={v.id}
                className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition-colors ${
                  isSelected
                    ? "border-blue-500 bg-blue-50 text-blue-700"
                    : isDisabled
                    ? "cursor-not-allowed border-gray-200 bg-gray-50 text-gray-400"
                    : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  disabled={isDisabled}
                  onChange={() => handleVersionToggle(v.id)}
                  className="accent-blue-500"
                />
                <span>{v.name}</span>
                <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">
                  {v.version_type}
                </span>
              </label>
            );
          })}
        </div>

        <button
          onClick={handleCompare}
          disabled={selectedVersionIds.length < 2 || isLoading}
          className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
        >
          {isLoading ? "Comparing..." : "Compare Versions"}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Comparison table */}
      {comparisonData && (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-100 px-4 py-3">
            <span className="text-sm font-semibold text-gray-700">
              Comparison Results
            </span>
            <span className="ml-2 text-sm text-gray-400">
              {sortedRows.length} row{sortedRows.length !== 1 ? "s" : ""}
            </span>
          </div>

          {sortedRows.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-gray-400">
              No data found for the selected versions.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th
                      className="sticky left-0 z-10 bg-gray-50 cursor-pointer px-4 py-3 text-left font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap"
                      onClick={() => handleSort("line_item_name")}
                    >
                      Line Item <SortIcon colKey="line_item_name" />
                    </th>
                    <th
                      className="cursor-pointer px-4 py-3 text-left font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap"
                      onClick={() => handleSort("dimension_key")}
                    >
                      Dimension <SortIcon colKey="dimension_key" />
                    </th>

                    {/* One column per version */}
                    {versionIds.map((vId) => (
                      <th
                        key={vId}
                        className="cursor-pointer px-4 py-3 text-right font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap"
                        onClick={() => handleSort(vId)}
                      >
                        {comparisonData.version_names[vId] ?? vId}
                        <SortIcon colKey={vId} />
                      </th>
                    ))}

                    {/* Diff columns only for 2-version comparisons */}
                    {versionIds.length === 2 && (
                      <>
                        <th
                          className="cursor-pointer px-4 py-3 text-right font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap"
                          onClick={() => handleSort("absolute_diff")}
                        >
                          Abs. Diff <SortIcon colKey="absolute_diff" />
                        </th>
                        <th
                          className="cursor-pointer px-4 py-3 text-right font-medium text-gray-600 hover:text-gray-900 whitespace-nowrap"
                          onClick={() => handleSort("percentage_diff")}
                        >
                          % Diff <SortIcon colKey="percentage_diff" />
                        </th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, idx) => (
                    <tr
                      key={`${row.line_item_id}__${row.dimension_key}`}
                      className={`border-b border-gray-100 hover:bg-blue-50/30 ${
                        idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"
                      }`}
                    >
                      <td className="sticky left-0 z-10 bg-inherit px-4 py-2.5 font-medium text-gray-700 whitespace-nowrap">
                        {row.line_item_name}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-xs text-gray-500 whitespace-nowrap max-w-[200px] truncate">
                        {row.dimension_key || "—"}
                      </td>

                      {versionIds.map((vId) => (
                        <td key={vId} className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {formatValue(row.values[vId] ?? null)}
                        </td>
                      ))}

                      {versionIds.length === 2 && (
                        <>
                          <td className={`px-4 py-2.5 text-right tabular-nums ${diffColor(row.absolute_diff)}`}>
                            {formatDiff(row.absolute_diff, false)}
                          </td>
                          <td className={`px-4 py-2.5 text-right tabular-nums ${diffColor(row.percentage_diff)}`}>
                            {formatDiff(row.percentage_diff, true)}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
