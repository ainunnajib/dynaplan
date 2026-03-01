"use client";

import { useState, useCallback } from "react";
import type { ChartConfig, ChartType } from "./ChartTypes";
import { ChartWidget } from "./ChartWidget";

// ── Palette ─────────────────────────────────────────────────────────────────

const COLOR_PALETTE = [
  "#6366f1",
  "#f59e0b",
  "#10b981",
  "#ef4444",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#84cc16",
];

const CHART_TYPES: { value: ChartType; label: string }[] = [
  { value: "bar", label: "Bar" },
  { value: "line", label: "Line" },
  { value: "area", label: "Area" },
  { value: "pie", label: "Pie / Donut" },
  { value: "waterfall", label: "Waterfall" },
  { value: "combo", label: "Combo (Bar + Line)" },
];

// ── Sample data generators ────────────────────────────────────────────────────

const SAMPLE_DATA = [
  { month: "Jan", revenue: 4200, expenses: 3100, profit: 1100 },
  { month: "Feb", revenue: 5800, expenses: 3400, profit: 2400 },
  { month: "Mar", revenue: 5100, expenses: 3700, profit: 1400 },
  { month: "Apr", revenue: 6300, expenses: 3900, profit: 2400 },
  { month: "May", revenue: 7200, expenses: 4100, profit: 3100 },
  { month: "Jun", revenue: 6800, expenses: 4400, profit: 2400 },
];

const DEFAULT_CONFIG: ChartConfig = {
  type: "bar",
  title: "Revenue vs Expenses",
  data: SAMPLE_DATA,
  xAxisKey: "month",
  yAxisKeys: ["revenue", "expenses"],
  colors: COLOR_PALETTE,
  showLegend: true,
  showGrid: true,
  stacked: false,
};

// ── Sub-components ───────────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-gray-600 mb-1">
      {children}
    </label>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mt-4 mb-2">
      {children}
    </p>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        role="switch"
        aria-checked={checked}
        className={`relative w-8 h-4 rounded-full transition-colors ${
          checked ? "bg-indigo-500" : "bg-gray-300"
        }`}
        onClick={() => onChange(!checked)}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </div>
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}

// ── Available y-axis keys derived from data ──────────────────────────────────

function getNumericKeys(data: ChartConfig["data"], xAxisKey: string): string[] {
  const first = data[0];
  if (!first) return [];
  return Object.keys(first).filter(
    (k) => k !== xAxisKey && typeof first[k] === "number"
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface ChartConfigPanelProps {
  initialConfig?: ChartConfig;
  /** Called when the user saves/applies the configuration */
  onSave?: (config: ChartConfig) => void;
  /** Called when the user cancels */
  onCancel?: () => void;
}

export function ChartConfigPanel({
  initialConfig = DEFAULT_CONFIG,
  onSave,
  onCancel,
}: ChartConfigPanelProps) {
  const [config, setConfig] = useState<ChartConfig>(initialConfig);

  const update = useCallback(
    <K extends keyof ChartConfig>(key: K, value: ChartConfig[K]) => {
      setConfig((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const availableKeys = getNumericKeys(config.data, config.xAxisKey);

  const toggleYKey = (key: string) => {
    setConfig((prev) => {
      const next = prev.yAxisKeys.includes(key)
        ? prev.yAxisKeys.filter((k) => k !== key)
        : [...prev.yAxisKeys, key];
      return { ...prev, yAxisKeys: next.length ? next : prev.yAxisKeys };
    });
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 p-6 bg-gray-50 rounded-xl">
      {/* ── Left panel: controls ─────────────────────────────────────────── */}
      <div className="w-full lg:w-72 shrink-0 space-y-3">
        <h2 className="text-base font-semibold text-gray-800">
          Chart configuration
        </h2>

        {/* Title */}
        <div>
          <Label>Title</Label>
          <input
            type="text"
            value={config.title ?? ""}
            onChange={(e) => update("title", e.target.value)}
            placeholder="Chart title"
            className="w-full text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        {/* Chart type */}
        <div>
          <Label>Chart type</Label>
          <select
            value={config.type}
            onChange={(e) => update("type", e.target.value as ChartType)}
            className="w-full text-sm border border-gray-200 rounded-md px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            {CHART_TYPES.map((ct) => (
              <option key={ct.value} value={ct.value}>
                {ct.label}
              </option>
            ))}
          </select>
        </div>

        {/* X-axis key */}
        <div>
          <Label>Category (X-axis) key</Label>
          <input
            type="text"
            value={config.xAxisKey}
            onChange={(e) => update("xAxisKey", e.target.value)}
            className="w-full text-sm border border-gray-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>

        {/* Y-axis series */}
        {availableKeys.length > 0 && (
          <div>
            <Label>Series (Y-axis)</Label>
            <div className="space-y-1">
              {availableKeys.map((key) => (
                <label
                  key={key}
                  className="flex items-center gap-2 text-sm cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={config.yAxisKeys.includes(key)}
                    onChange={() => toggleYKey(key)}
                    className="accent-indigo-500"
                  />
                  <span className="text-gray-700">{key}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Display options */}
        <SectionHeading>Display</SectionHeading>
        <div className="space-y-2">
          <Toggle
            checked={config.showLegend ?? true}
            onChange={(v) => update("showLegend", v)}
            label="Show legend"
          />
          <Toggle
            checked={config.showGrid ?? true}
            onChange={(v) => update("showGrid", v)}
            label="Show grid"
          />
          {(config.type === "bar" ||
            config.type === "area" ||
            config.type === "combo") && (
            <Toggle
              checked={config.stacked ?? false}
              onChange={(v) => update("stacked", v)}
              label="Stacked"
            />
          )}
          {config.type === "bar" && (
            <Toggle
              checked={config.horizontal ?? false}
              onChange={(v) => update("horizontal", v)}
              label="Horizontal"
            />
          )}
        </div>

        {/* Color palette */}
        <SectionHeading>Color palette</SectionHeading>
        <div className="flex flex-wrap gap-1.5">
          {COLOR_PALETTE.map((color) => {
            const isFirst = config.colors?.[0] === color;
            return (
              <button
                key={color}
                title={color}
                onClick={() => {
                  // Rotate palette so chosen color is first
                  const idx = COLOR_PALETTE.indexOf(color);
                  const rotated = [
                    ...COLOR_PALETTE.slice(idx),
                    ...COLOR_PALETTE.slice(0, idx),
                  ];
                  update("colors", rotated);
                }}
                className={`w-5 h-5 rounded-full border-2 transition-transform hover:scale-110 ${
                  isFirst ? "border-gray-800 scale-110" : "border-transparent"
                }`}
                style={{ backgroundColor: color }}
              />
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 pt-2">
          {onSave && (
            <button
              onClick={() => onSave(config)}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium py-1.5 rounded-md transition-colors"
            >
              Apply
            </button>
          )}
          {onCancel && (
            <button
              onClick={onCancel}
              className="flex-1 border border-gray-200 hover:bg-gray-100 text-gray-700 text-sm font-medium py-1.5 rounded-md transition-colors"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* ── Right panel: live preview ────────────────────────────────────── */}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Preview
        </p>
        <ChartWidget config={config} height={320} className="min-h-[360px]" />
      </div>
    </div>
  );
}
