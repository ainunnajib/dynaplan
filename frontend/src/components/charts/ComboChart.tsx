"use client";

import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { ChartConfig, SeriesConfig } from "./ChartTypes";

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

interface ComboChartProps {
  config: ChartConfig;
  /** Per-series render overrides. Index matches yAxisKeys order */
  series?: SeriesConfig[];
  height?: number;
}

export function ComboChart({ config, series = [], height = 320 }: ComboChartProps) {
  const {
    data,
    xAxisKey,
    yAxisKeys,
    colors = DEFAULT_COLORS,
    showLegend = true,
    showGrid = true,
    stacked = false,
  } = config;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={data}
        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
      >
        {showGrid && (
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        )}

        <XAxis dataKey={xAxisKey} tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />

        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: "6px",
            fontSize: 12,
          }}
        />

        {showLegend && <Legend wrapperStyle={{ fontSize: 12 }} />}

        {yAxisKeys.map((key, index) => {
          const override = series[index];
          const color =
            override?.color ?? colors[index % colors.length];
          const label = override?.label ?? key;
          const asBar = override?.asBar ?? index === 0;

          return asBar ? (
            <Bar
              key={key}
              dataKey={key}
              name={label}
              fill={color}
              stackId={stacked ? "stack" : undefined}
              radius={[3, 3, 0, 0]}
            />
          ) : (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              name={label}
              stroke={color}
              strokeWidth={override?.strokeWidth ?? 2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          );
        })}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
