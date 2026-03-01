"use client";

import { useState } from "react";
import { addWidget } from "@/lib/api";
import type { DashboardWidget, WidgetType } from "@/lib/api";

interface Props {
  dashboardId: string;
  onClose: () => void;
  onWidgetAdded: (widget: DashboardWidget) => void;
}

interface WidgetTypeOption {
  type: WidgetType;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const WIDGET_OPTIONS: WidgetTypeOption[] = [
  {
    type: "kpi_card",
    label: "KPI Card",
    description: "Display a single metric with optional change indicator",
    color: "bg-emerald-50 border-emerald-200 hover:border-emerald-400 hover:bg-emerald-100",
    icon: (
      <svg className="h-6 w-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
  },
  {
    type: "chart",
    label: "Chart",
    description: "Visualize data as bar, line, area, or pie chart",
    color: "bg-purple-50 border-purple-200 hover:border-purple-400 hover:bg-purple-100",
    icon: (
      <svg className="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0 0 20.25 18V6A2.25 2.25 0 0 0 18 3.75H6A2.25 2.25 0 0 0 3.75 6v12A2.25 2.25 0 0 0 6 20.25Z" />
      </svg>
    ),
  },
  {
    type: "grid",
    label: "Grid",
    description: "Embed a module grid view showing line item data",
    color: "bg-blue-50 border-blue-200 hover:border-blue-400 hover:bg-blue-100",
    icon: (
      <svg className="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25" />
      </svg>
    ),
  },
  {
    type: "text",
    label: "Text",
    description: "Add a free-form text block, notes, or instructions",
    color: "bg-amber-50 border-amber-200 hover:border-amber-400 hover:bg-amber-100",
    icon: (
      <svg className="h-6 w-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z" />
      </svg>
    ),
  },
  {
    type: "image",
    label: "Image",
    description: "Display an image from a URL",
    color: "bg-pink-50 border-pink-200 hover:border-pink-400 hover:bg-pink-100",
    icon: (
      <svg className="h-6 w-6 text-pink-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
      </svg>
    ),
  },
];

type Step = "select_type" | "configure";

export default function AddWidgetPanel({ dashboardId, onClose, onWidgetAdded }: Props) {
  const [step, setStep] = useState<Step>("select_type");
  const [selectedType, setSelectedType] = useState<WidgetType | null>(null);
  const [title, setTitle] = useState("");
  const [configText, setConfigText] = useState("{}");
  const [configError, setConfigError] = useState<string | null>(null);
  const [width, setWidth] = useState(6);
  const [height, setHeight] = useState(4);
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  function handleSelectType(type: WidgetType) {
    setSelectedType(type);
    // Pre-fill sensible default configs per type
    if (type === "kpi_card") {
      setConfigText(JSON.stringify({ label: "Metric", value: null }, null, 2));
      setWidth(3);
      setHeight(2);
    } else if (type === "chart") {
      setConfigText(JSON.stringify({ chart_type: "bar", module_id: null, line_item_id: null }, null, 2));
      setWidth(6);
      setHeight(4);
    } else if (type === "grid") {
      setConfigText(JSON.stringify({ module_id: null }, null, 2));
      setWidth(12);
      setHeight(6);
    } else if (type === "text") {
      setConfigText(JSON.stringify({ content: "Add your text here..." }, null, 2));
      setWidth(4);
      setHeight(3);
    } else if (type === "image") {
      setConfigText(JSON.stringify({ src: "", alt: "Image" }, null, 2));
      setWidth(4);
      setHeight(3);
    }
    setStep("configure");
  }

  async function handleAdd() {
    if (!selectedType) return;

    let config: Record<string, unknown> = {};
    try {
      config = JSON.parse(configText);
    } catch {
      setConfigError("Invalid JSON configuration");
      return;
    }
    setConfigError(null);
    setIsAdding(true);
    setAddError(null);

    try {
      const widget = await addWidget(dashboardId, {
        widget_type: selectedType,
        title: title.trim() || undefined,
        config,
        position_x: 0,
        position_y: 0,
        width,
        height,
      });
      onWidgetAdded(widget);
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add widget");
    } finally {
      setIsAdding(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
          <div className="flex items-center gap-2">
            {step === "configure" && (
              <button
                type="button"
                onClick={() => setStep("select_type")}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors"
              >
                <ChevronLeftIcon className="h-4 w-4" />
              </button>
            )}
            <h2 className="text-base font-semibold text-zinc-900">
              {step === "select_type" ? "Add Widget" : "Configure Widget"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {step === "select_type" ? (
            <div>
              <p className="mb-4 text-sm text-zinc-500">Choose the type of widget to add to your dashboard.</p>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {WIDGET_OPTIONS.map((opt) => (
                  <button
                    key={opt.type}
                    type="button"
                    onClick={() => handleSelectType(opt.type)}
                    className={`flex items-start gap-3 rounded-lg border p-4 text-left transition-all ${opt.color}`}
                  >
                    <div className="shrink-0 mt-0.5">{opt.icon}</div>
                    <div>
                      <div className="text-sm font-semibold text-zinc-900">{opt.label}</div>
                      <div className="mt-0.5 text-xs text-zinc-500">{opt.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Title <span className="text-zinc-400">(optional)</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Total Revenue"
                  className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                />
              </div>

              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-zinc-700 mb-1">
                    Width <span className="text-zinc-400">(1–12 cols)</span>
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={width}
                    onChange={(e) => setWidth(Math.max(1, Math.min(12, parseInt(e.target.value) || 1)))}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-xs font-medium text-zinc-700 mb-1">
                    Height <span className="text-zinc-400">(rows)</span>
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={height}
                    onChange={(e) => setHeight(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
                    className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">
                  Configuration <span className="text-zinc-400">(JSON)</span>
                </label>
                <textarea
                  value={configText}
                  onChange={(e) => {
                    setConfigText(e.target.value);
                    setConfigError(null);
                  }}
                  rows={5}
                  className={`w-full rounded-md border px-3 py-2 font-mono text-xs text-zinc-900 focus:outline-none focus:ring-1 resize-none ${
                    configError
                      ? "border-red-300 focus:border-red-500 focus:ring-red-500"
                      : "border-zinc-300 focus:border-violet-500 focus:ring-violet-500"
                  }`}
                  spellCheck={false}
                />
                {configError && (
                  <p className="mt-1 text-xs text-red-600">{configError}</p>
                )}
                <p className="mt-1 text-xs text-zinc-400">
                  Edit the JSON to configure widget data sources, labels, and appearance.
                </p>
              </div>

              {addError && (
                <p className="text-xs text-red-600">{addError}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {step === "configure" && (
          <div className="flex items-center justify-end gap-2 border-t border-zinc-200 px-6 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isAdding}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleAdd}
              disabled={isAdding}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {isAdding ? "Adding..." : "Add Widget"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
