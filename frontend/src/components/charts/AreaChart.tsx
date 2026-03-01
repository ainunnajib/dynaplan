"use client";

import {
  AreaChart as RechartsAreaChart,
  Area,
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

interface AreaChartProps {
  config: ChartConfig;
  height?: number;
  /** Area fill opacity passed directly to the gradient stops (0–1) */
  fillOpacity?: number;
}

export function AreaChart({
  config,
  height = 300,
  fillOpacity = 0.25,
}: AreaChartProps) {
  const {
    data,
    xAxisKey,
    yAxisKeys,
    colors = DEFAULT_COLORS,
    showLegend = true,
    showGrid = true,
    stacked = false,
  } = config;

  const resolvedColors = yAxisKeys.map(
    (_, i) => colors[i % colors.length]
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsAreaChart
        data={data}
        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
      >
        {/* SVG gradient definitions — using native SVG defs inside recharts */}
        <defs>
          {resolvedColors.map((color, i) => (
            <linearGradient
              key={`area-grad-${i}`}
              id={`area-grad-${i}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="5%"
                stopColor={color}
                stopOpacity={fillOpacity}
              />
              <stop offset="95%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>

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
          <Area
            key={key}
            type="monotone"
            dataKey={key}
            name={key}
            stroke={resolvedColors[index]}
            strokeWidth={2}
            fill={`url(#area-grad-${index})`}
            stackId={stacked ? "stack" : undefined}
          />
        ))}
      </RechartsAreaChart>
    </ResponsiveContainer>
  );
}
