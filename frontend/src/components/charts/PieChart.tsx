"use client";

import { useState, useCallback } from "react";
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Sector,
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

// recharts passes these props to the active-shape renderer
interface ActiveShapeProps {
  cx?: number;
  cy?: number;
  innerRadius?: number;
  outerRadius?: number;
  startAngle?: number;
  endAngle?: number;
  fill?: string;
  payload?: Record<string, unknown>;
  value?: number | string;
}

function ActiveShape({
  cx = 0,
  cy = 0,
  innerRadius = 0,
  outerRadius = 0,
  startAngle,
  endAngle,
  fill,
  payload,
  value,
}: ActiveShapeProps) {
  return (
    <g>
      <text
        x={cx}
        y={cy}
        dy={-6}
        textAnchor="middle"
        fill="#111827"
        fontSize={13}
        fontWeight={600}
      >
        {String(payload?.name ?? "")}
      </text>
      <text
        x={cx}
        y={cy}
        dy={14}
        textAnchor="middle"
        fill="#6b7280"
        fontSize={12}
      >
        {typeof value === "number" ? value.toLocaleString() : String(value ?? "")}
      </text>

      {/* Expanded outer sector */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />

      {/* Accent ring */}
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={outerRadius + 10}
        outerRadius={outerRadius + 14}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
      />
    </g>
  );
}

interface PieChartProps {
  config: ChartConfig;
  height?: number;
  /** 0 = full pie, 0.5 = donut with 50 % inner radius */
  innerRadius?: number;
}

export function PieChart({ config, height = 320, innerRadius }: PieChartProps) {
  const {
    data,
    xAxisKey,
    yAxisKeys,
    colors = DEFAULT_COLORS,
    showLegend = true,
  } = config;

  const valueKey = yAxisKeys[0] ?? "value";
  const resolvedInnerRadius = innerRadius ?? config.innerRadius ?? 0;

  const [activeIndex, setActiveIndex] = useState<number | undefined>(
    undefined
  );

  const onMouseEnter = useCallback((_: unknown, index: number) => {
    setActiveIndex(index);
  }, []);

  const onMouseLeave = useCallback(() => {
    setActiveIndex(undefined);
  }, []);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsPieChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <Pie
          data={data}
          dataKey={valueKey}
          nameKey={xAxisKey}
          cx="50%"
          cy="50%"
          innerRadius={`${Math.round(resolvedInnerRadius * 100)}%`}
          outerRadius="70%"
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          {...({ activeIndex, activeShape: ActiveShape as any } as any)}
          onMouseEnter={onMouseEnter}
          onMouseLeave={onMouseLeave}
        >
          {data.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={colors[index % colors.length]}
              stroke="none"
            />
          ))}
        </Pie>

        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: "6px",
            fontSize: 12,
          }}
        />

        {showLegend && (
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            iconType="circle"
          />
        )}
      </RechartsPieChart>
    </ResponsiveContainer>
  );
}
