"use client";

import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
export interface WaterfallItem {
  /** Category label (X-axis) */
  name: string;
  /** Absolute value of this bar's change */
  value: number;
  /** Mark as a running total bar (rendered in blue) */
  isTotal?: boolean;
}

interface WaterfallChartProps {
  items: WaterfallItem[];
  height?: number;
  showGrid?: boolean;
  showLegend?: boolean;
  /** Starting baseline (default 0) */
  start?: number;
  /** Color for positive change bars */
  positiveColor?: string;
  /** Color for negative change bars */
  negativeColor?: string;
  /** Color for total bars */
  totalColor?: string;
  /** Color for the invisible offset bar (must be transparent) */
  offsetColor?: string;
}

interface WaterfallRow {
  name: string;
  /** Invisible offset to lift the visible bar off the axis */
  offset: number;
  /** Positive or total value */
  increase: number;
  /** Negative (absolute) value */
  decrease: number;
  /** Running total for reference */
  runningTotal: number;
  isTotal: boolean;
}

function buildWaterfallData(
  items: WaterfallItem[],
  start: number
): WaterfallRow[] {
  const rows: WaterfallRow[] = [];
  let running = start;

  for (const item of items) {
    const prev = running;

    if (item.isTotal) {
      rows.push({
        name: item.name,
        offset: 0,
        increase: running,
        decrease: 0,
        runningTotal: running,
        isTotal: true,
      });
    } else if (item.value >= 0) {
      running += item.value;
      rows.push({
        name: item.name,
        offset: prev,
        increase: item.value,
        decrease: 0,
        runningTotal: running,
        isTotal: false,
      });
    } else {
      running += item.value; // item.value is negative
      rows.push({
        name: item.name,
        offset: running, // bottom of the red bar
        increase: 0,
        decrease: Math.abs(item.value),
        runningTotal: running,
        isTotal: false,
      });
    }
  }

  return rows;
}

export function WaterfallChart({
  items,
  height = 320,
  showGrid = true,
  showLegend = true,
  start = 0,
  positiveColor = "#10b981",
  negativeColor = "#ef4444",
  totalColor = "#3b82f6",
  offsetColor = "transparent",
}: WaterfallChartProps) {
  const data = buildWaterfallData(items, start);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart
        data={data}
        margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
      >
        {showGrid && (
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        )}

        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />

        <Tooltip
          contentStyle={{
            background: "#fff",
            border: "1px solid #e5e7eb",
            borderRadius: "6px",
            fontSize: 12,
          }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={((value: number, name: string): [string, string] | null => {
            if (name === "offset") return null;
            return [value.toLocaleString(), name];
          }) as any}
        />

        {showLegend && (
          <Legend
            wrapperStyle={{ fontSize: 12 }}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            {...({ payload: [
              { value: "Increase", type: "square" as const, color: positiveColor },
              { value: "Decrease", type: "square" as const, color: negativeColor },
              { value: "Total", type: "square" as const, color: totalColor },
            ] } as any)}
          />
        )}

        <ReferenceLine y={0} stroke="#9ca3af" />

        {/* Invisible offset bar — lifts the visible bars */}
        <Bar dataKey="offset" stackId="waterfall" fill={offsetColor} />

        {/* Positive / increase bars */}
        <Bar dataKey="increase" stackId="waterfall" name="Increase" radius={[3, 3, 0, 0]}>
          {data.map((row, index) => (
            <Cell
              key={`inc-${index}`}
              fill={row.isTotal ? totalColor : positiveColor}
            />
          ))}
        </Bar>

        {/* Negative / decrease bars */}
        <Bar dataKey="decrease" stackId="waterfall" name="Decrease" radius={[3, 3, 0, 0]}>
          {data.map((_, index) => (
            <Cell key={`dec-${index}`} fill={negativeColor} />
          ))}
        </Bar>
      </ComposedChart>
    </ResponsiveContainer>
  );
}
