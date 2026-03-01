"use client";

import { useState } from "react";
import type { ChartConfig } from "./ChartTypes";
import { BarChart } from "./BarChart";
import { LineChart } from "./LineChart";
import { AreaChart } from "./AreaChart";
import { PieChart } from "./PieChart";
import { WaterfallChart } from "./WaterfallChart";
import type { WaterfallItem } from "./WaterfallChart";
import { ComboChart } from "./ComboChart";

interface ChartWidgetProps {
  config: ChartConfig;
  height?: number;
  className?: string;
  onEditClick?: () => void;
}

/** Converts generic ChartConfig data into WaterfallItem array */
function toWaterfallItems(config: ChartConfig): WaterfallItem[] {
  const valueKey = config.yAxisKeys[0] ?? "value";
  return config.data.map((row) => ({
    name: String(row[config.xAxisKey] ?? ""),
    value: Number(row[valueKey] ?? 0),
    isTotal: Boolean(row["isTotal"]),
  }));
}

function ChartRenderer({
  config,
  height,
}: {
  config: ChartConfig;
  height: number;
}) {
  switch (config.type) {
    case "bar":
      return <BarChart config={config} height={height} />;
    case "line":
      return <LineChart config={config} height={height} />;
    case "area":
      return <AreaChart config={config} height={height} />;
    case "pie":
      return <PieChart config={config} height={height} />;
    case "waterfall":
      return (
        <WaterfallChart
          items={toWaterfallItems(config)}
          height={height}
          showGrid={config.showGrid}
          showLegend={config.showLegend}
        />
      );
    case "combo":
      return <ComboChart config={config} height={height} />;
    default:
      return (
        <div className="flex items-center justify-center h-full text-sm text-gray-400">
          Unknown chart type
        </div>
      );
  }
}

export function ChartWidget({
  config,
  height = 300,
  className = "",
  onEditClick,
}: ChartWidgetProps) {
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  return (
    <div
      className={`bg-white border border-gray-200 rounded-xl shadow-sm flex flex-col overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800 truncate">
          {config.title ?? "Chart"}
        </h3>

        <div className="flex items-center gap-1">
          {/* Edit button */}
          {onEditClick && (
            <button
              onClick={onEditClick}
              className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              aria-label="Edit chart"
            >
              {/* Pencil icon */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
          )}

          {/* Export button (placeholder) */}
          <div className="relative">
            <button
              onClick={() => setExportMenuOpen((v) => !v)}
              className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              aria-label="Export chart"
            >
              {/* Download icon */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </button>

            {exportMenuOpen && (
              <>
                {/* Backdrop */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setExportMenuOpen(false)}
                />
                <div className="absolute right-0 top-8 z-20 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[130px]">
                  {(["PNG", "SVG", "CSV"] as const).map((fmt) => (
                    <button
                      key={fmt}
                      className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                      onClick={() => {
                        // Export functionality — placeholder
                        console.log(`Export as ${fmt} — not yet implemented`);
                        setExportMenuOpen(false);
                      }}
                    >
                      Export as {fmt}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Chart body */}
      <div className="flex-1 p-3">
        <ChartRenderer config={config} height={height} />
      </div>
    </div>
  );
}
