// Chart type definitions for F016 — Charts & visualizations

export type ChartType = "bar" | "line" | "area" | "pie" | "waterfall" | "combo";

export interface ChartDataPoint {
  [key: string]: string | number;
}

export interface SeriesConfig {
  /** The key in ChartDataPoint to read values from */
  key: string;
  /** Display label for this series */
  label?: string;
  /** Hex color string, e.g. "#6366f1" */
  color?: string;
  /** For combo charts: whether this series is a bar (vs line) */
  asBar?: boolean;
  /** Stroke width for line/area charts */
  strokeWidth?: number;
  /** Fill opacity for area charts (0–1) */
  fillOpacity?: number;
}

export interface ChartConfig {
  /** Chart variant */
  type: ChartType;
  /** Chart heading */
  title?: string;
  /** Data rows */
  data: ChartDataPoint[];
  /** Key used for the category / X-axis */
  xAxisKey: string;
  /** Keys used for the value / Y-axis series */
  yAxisKeys: string[];
  /** Optional per-series color overrides (indexed to match yAxisKeys) */
  colors?: string[];
  /** Show legend */
  showLegend?: boolean;
  /** Show grid lines */
  showGrid?: boolean;
  /** Stack series on top of each other */
  stacked?: boolean;
  /** Render bars horizontally (bar chart only) */
  horizontal?: boolean;
  /** Inner radius ratio for donut / pie charts (0 = full pie) */
  innerRadius?: number;
}
