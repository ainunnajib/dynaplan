"use client";

import { useCallback, useState } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface LineItemOption {
  id: string;
  name: string;
}

interface ComparisonMatrixData {
  line_item_id: string;
  version_names: Record<string, string>;
  matrix: Record<string, Record<string, number | null>>;
  dimension_keys: string[];
}

interface ComparisonMatrixProps {
  modelId: string;
  availableVersions: Version[];
  availableLineItems: LineItemOption[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function getMinMax(matrix: ComparisonMatrixData["matrix"]): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const versionVals of Object.values(matrix)) {
    for (const val of Object.values(versionVals)) {
      if (val !== null) {
        if (val < min) min = val;
        if (val > max) max = val;
      }
    }
  }
  if (min === Infinity) return { min: 0, max: 0 };
  return { min, max };
}

/**
 * Maps a value to a blue color intensity (0 = white, 1 = dark blue).
 * Returns a CSS color string.
 */
function valueToHeatColor(value: number | null, min: number, max: number): string {
  if (value === null) return "#f9fafb"; // gray-50 for missing
  const range = max - min;
  if (range === 0) return "#dbeafe"; // light blue if all values are the same
  const intensity = (value - min) / range; // 0 to 1
  // Interpolate from white (#ffffff) to blue-700 (#1d4ed8)
  const r = Math.round(255 - intensity * (255 - 29));
  const g = Math.round(255 - intensity * (255 - 78));
  const b = Math.round(255 - intensity * (255 - 216));
  return `rgb(${r}, ${g}, ${b})`;
}

function textColorForBg(value: number | null, min: number, max: number): string {
  if (value === null) return "#9ca3af"; // gray-400
  const range = max - min;
  if (range === 0) return "#1e40af";
  const intensity = (value - min) / range;
  return intensity > 0.6 ? "#ffffff" : "#1e3a5f";
}

function formatValue(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  content: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ComparisonMatrix({
  modelId,
  availableVersions,
  availableLineItems,
}: ComparisonMatrixProps) {
  const [selectedVersionIds, setSelectedVersionIds] = useState<string[]>([]);
  const [selectedLineItemId, setSelectedLineItemId] = useState<string>("");
  const [matrixData, setMatrixData] = useState<ComparisonMatrixData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    content: "",
  });

  const handleVersionToggle = useCallback((versionId: string) => {
    setSelectedVersionIds((prev) => {
      if (prev.includes(versionId)) {
        return prev.filter((id) => id !== versionId);
      }
      if (prev.length >= 6) return prev; // max 6 versions in matrix
      return [...prev, versionId];
    });
    setMatrixData(null);
  }, []);

  const handleFetch = useCallback(async () => {
    if (selectedVersionIds.length < 1) {
      setError("Please select at least one version.");
      return;
    }
    if (!selectedLineItemId) {
      setError("Please select a line item.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<ComparisonMatrixData>(
        `/models/${modelId}/compare/matrix`,
        {
          method: "POST",
          body: JSON.stringify({
            version_ids: selectedVersionIds,
            line_item_id: selectedLineItemId,
          }),
        }
      );
      setMatrixData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch matrix data");
    } finally {
      setIsLoading(false);
    }
  }, [modelId, selectedVersionIds, selectedLineItemId]);

  const { min, max } = matrixData ? getMinMax(matrixData.matrix) : { min: 0, max: 0 };

  const handleCellMouseEnter = useCallback(
    (e: React.MouseEvent, dimKey: string, versionId: string, value: number | null) => {
      const rect = (e.target as HTMLElement).getBoundingClientRect();
      setTooltip({
        visible: true,
        x: rect.left + rect.width / 2,
        y: rect.top - 8,
        content: `${dimKey || "(no dim)"} | ${versionId}: ${formatValue(value)}`,
      });
    },
    []
  );

  const handleCellMouseLeave = useCallback(() => {
    setTooltip((t) => ({ ...t, visible: false }));
  }, []);

  const versionIds = matrixData ? selectedVersionIds : [];

  return (
    <div className="flex flex-col gap-4">
      {/* Controls */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">
          Comparison Matrix — Single Line Item Heatmap
        </h2>

        <div className="flex flex-col gap-3">
          {/* Line item selector */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500">Line Item</label>
            <select
              value={selectedLineItemId}
              onChange={(e) => {
                setSelectedLineItemId(e.target.value);
                setMatrixData(null);
              }}
              className="max-w-xs rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select a line item...</option>
              {availableLineItems.map((li) => (
                <option key={li.id} value={li.id}>
                  {li.name}
                </option>
              ))}
            </select>
          </div>

          {/* Version checkboxes */}
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-gray-500">
              Versions (select 1 or more)
            </label>
            <div className="flex flex-wrap gap-2">
              {availableVersions.map((v) => {
                const isSelected = selectedVersionIds.includes(v.id);
                return (
                  <label
                    key={v.id}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-xs transition-colors ${
                      isSelected
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => handleVersionToggle(v.id)}
                      className="accent-blue-500"
                    />
                    {v.name}
                  </label>
                );
              })}
            </div>
          </div>

          <button
            onClick={handleFetch}
            disabled={selectedVersionIds.length === 0 || !selectedLineItemId || isLoading}
            className="w-fit rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
          >
            {isLoading ? "Loading..." : "Build Matrix"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="pointer-events-none fixed z-50 rounded-md bg-gray-900 px-2.5 py-1.5 text-xs text-white shadow-lg"
          style={{
            left: tooltip.x,
            top: tooltip.y,
            transform: "translateX(-50%) translateY(-100%)",
          }}
        >
          {tooltip.content}
        </div>
      )}

      {/* Heatmap matrix */}
      {matrixData && (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-100 px-4 py-3">
            <span className="text-sm font-semibold text-gray-700">Heatmap</span>
            <span className="ml-2 text-sm text-gray-400">
              {matrixData.dimension_keys.length} dimension intersection
              {matrixData.dimension_keys.length !== 1 ? "s" : ""}
            </span>
          </div>

          {matrixData.dimension_keys.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-gray-400">
              No cell data found for this line item and the selected versions.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="px-4 py-3 text-left font-medium text-gray-600 whitespace-nowrap">
                      Dimension
                    </th>
                    {versionIds.map((vId) => (
                      <th
                        key={vId}
                        className="px-4 py-3 text-center font-medium text-gray-600 whitespace-nowrap"
                      >
                        {matrixData.version_names[vId] ?? vId}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixData.dimension_keys.map((dimKey, rowIdx) => (
                    <tr
                      key={dimKey}
                      className={`border-b border-gray-100 ${
                        rowIdx % 2 === 0 ? "bg-white" : "bg-gray-50/30"
                      }`}
                    >
                      <td className="px-4 py-2 font-mono text-gray-500 whitespace-nowrap max-w-[200px] truncate">
                        {dimKey || "(global)"}
                      </td>
                      {versionIds.map((vId) => {
                        const cellValue = matrixData.matrix[dimKey]?.[vId] ?? null;
                        const bgColor = valueToHeatColor(cellValue, min, max);
                        const txtColor = textColorForBg(cellValue, min, max);
                        return (
                          <td
                            key={vId}
                            className="px-3 py-2 text-center tabular-nums cursor-default transition-opacity hover:opacity-80"
                            style={{ backgroundColor: bgColor, color: txtColor }}
                            onMouseEnter={(e) =>
                              handleCellMouseEnter(e, dimKey, matrixData.version_names[vId] ?? vId, cellValue)
                            }
                            onMouseLeave={handleCellMouseLeave}
                          >
                            {formatValue(cellValue)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Color scale legend */}
          {matrixData.dimension_keys.length > 0 && (
            <div className="border-t border-gray-100 px-4 py-3 flex items-center gap-3">
              <span className="text-xs text-gray-500">Value scale:</span>
              <div className="flex items-center gap-1">
                <div
                  className="h-4 w-16 rounded-sm"
                  style={{
                    background: `linear-gradient(to right, ${valueToHeatColor(min, min, max)}, ${valueToHeatColor(max, min, max)})`,
                  }}
                />
                <span className="text-xs text-gray-400">{formatValue(min)}</span>
                <span className="text-xs text-gray-400 mx-1">to</span>
                <span className="text-xs text-gray-400">{formatValue(max)}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
