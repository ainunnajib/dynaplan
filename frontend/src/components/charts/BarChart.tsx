"use client";

import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ChartConfig } from "./ChartTypes";

const DEFAULT_COLORS = [
  "#6366f1",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
];

interface BarChartProps {
  config: ChartConfig;
  height?: number;
}

export function BarChart({ config, height = 300 }: BarChartProps) {
  const {
    data,
    xAxisKey,
    yAxisKeys,
    colors = DEFAULT_COLORS,
    showLegend = true,
    showGrid = true,
    stacked = false,
    horizontal = false,
  } = config;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsBarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
      >
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#e5e7eb"
            vertical={!horizontal}
            horizontal={horizontal}
          />
        )}

        {horizontal ? (
          <>
            <XAxis type="number" tick={{ fontSize: 12 }} />
            <YAxis
              dataKey={xAxisKey}
              type="category"
              width={100}
              tick={{ fontSize: 12 }}
            />
          </>
        ) : (
          <>
            <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
          </>
        )}

        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: "6px",
            fontSize: 12,
          }}
        />

        {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}

        {yAxisKeys.map((key, index) => (
          <Bar
            key={key}
            dataKey={key}
            name={key}
            fill={colors[index % colors.length]}
            stackId={stacked ? "stack" : undefined}
            radius={stacked ? undefined : [3, 3, 0, 0]}
          >
            {/* Per-bar cell coloring when there is only one series */}
            {yAxisKeys.length === 1
              ? data.map((_, i) => (
                  <Cell
                    key={`cell-${i}`}
                    fill={colors[i % colors.length]}
                  />
                ))
              : null}
          </Bar>
        ))}
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
