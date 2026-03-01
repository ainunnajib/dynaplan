"use client";

import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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

interface LineChartProps {
  config: ChartConfig;
  height?: number;
  /** Smooth curve (monotone) vs straight segments */
  smooth?: boolean;
  strokeWidth?: number;
  showDots?: boolean;
}

export function LineChart({
  config,
  height = 300,
  smooth = true,
  strokeWidth = 2,
  showDots = true,
}: LineChartProps) {
  const {
    data,
    xAxisKey,
    yAxisKeys,
    colors = DEFAULT_COLORS,
    showLegend = true,
    showGrid = true,
  } = config;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsLineChart
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

        {yAxisKeys.map((key, index) => (
          <Line
            key={key}
            type={smooth ? "monotone" : "linear"}
            dataKey={key}
            name={key}
            stroke={colors[index % colors.length]}
            strokeWidth={strokeWidth}
            dot={showDots ? { r: 3 } : false}
            activeDot={{ r: 5 }}
          />
        ))}
      </RechartsLineChart>
    </ResponsiveContainer>
  );
}
