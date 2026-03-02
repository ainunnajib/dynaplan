"use client";

import { useMemo, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CardType = "grid" | "chart" | "button" | "kpi" | "text" | "image" | "filter";

export interface UXCardData {
  id: string;
  page_id: string;
  card_type: CardType;
  title: string | null;
  config: Record<string, unknown> | null;
  position_x: number;
  position_y: number;
  width: number;
  height: number;
  sort_order: number;
}

interface PageCardProps {
  card: UXCardData;
  isEditMode: boolean;
  contextValues?: Record<string, string[]>;
  linkedFilter?: string | null;
  onDelete?: (cardId: string) => void;
  onUpdate?: (cardId: string, patch: Partial<UXCardData>) => void;
  onEmitLink?: (
    sourceCardId: string,
    value: string | null,
    targetCardIds: string[]
  ) => void;
  onNavigatePage?: (targetPageId: string) => void;
}

// ---------------------------------------------------------------------------
// Label / color maps
// ---------------------------------------------------------------------------

const CARD_TYPE_LABELS: Record<CardType, string> = {
  grid: "Grid",
  chart: "Chart",
  button: "Button",
  kpi: "KPI",
  text: "Text",
  image: "Image",
  filter: "Filter",
};

const CARD_TYPE_COLORS: Record<CardType, string> = {
  grid: "bg-blue-50 text-blue-600",
  chart: "bg-purple-50 text-purple-600",
  button: "bg-indigo-50 text-indigo-600",
  kpi: "bg-emerald-50 text-emerald-600",
  text: "bg-amber-50 text-amber-600",
  image: "bg-pink-50 text-pink-600",
  filter: "bg-cyan-50 text-cyan-600",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PageCard({
  card,
  isEditMode,
  contextValues = {},
  linkedFilter = null,
  onDelete,
  onUpdate,
  onEmitLink,
  onNavigatePage,
}: PageCardProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  return (
    <div
      className={`group relative flex h-full w-full flex-col overflow-hidden rounded-lg border bg-white shadow-sm transition-shadow ${
        isEditMode
          ? "border-violet-300 hover:shadow-md"
          : "border-zinc-200"
      }`}
    >
      {/* Header */}
      <div
        className={`flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 ${
          isEditMode
            ? "border-violet-100 bg-violet-50/50"
            : "border-zinc-100 bg-zinc-50"
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
              CARD_TYPE_COLORS[card.card_type]
            }`}
          >
            {CARD_TYPE_LABELS[card.card_type]}
          </span>
          <span className="truncate text-xs font-medium text-zinc-700">
            {card.title ?? ""}
          </span>
        </div>

        {isEditMode && (
          <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="rounded p-1 text-zinc-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              title="Delete card"
            >
              <TrashIcon className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto p-3">
        <CardBody
          card={card}
          contextValues={contextValues}
          linkedFilter={linkedFilter}
          onEmitLink={onEmitLink}
          onNavigatePage={onNavigatePage}
        />
      </div>

      {/* Delete confirmation */}
      {showDeleteConfirm && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-lg bg-white/95 p-4 text-center backdrop-blur-sm">
          <p className="text-xs font-semibold text-zinc-800">Delete card?</p>
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                onDelete?.(card.id);
                setShowDeleteConfirm(false);
              }}
              className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
            >
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Card body renderer
// ---------------------------------------------------------------------------

interface CardBodyProps {
  card: UXCardData;
  contextValues: Record<string, string[]>;
  linkedFilter: string | null;
  onEmitLink?: (
    sourceCardId: string,
    value: string | null,
    targetCardIds: string[]
  ) => void;
  onNavigatePage?: (targetPageId: string) => void;
}

interface DataPoint {
  label: string;
  value: number;
}

function CardBody({
  card,
  contextValues,
  linkedFilter,
  onEmitLink,
  onNavigatePage,
}: CardBodyProps) {
  const config = card.config ?? {};
  const linkTargets = asStringArray(config.link_targets);
  const contextTokens = useMemo(
    () =>
      Object.values(contextValues)
        .flat()
        .map((token) => token.trim().toLowerCase())
        .filter((token) => token.length > 0),
    [contextValues]
  );

  if (card.card_type === "kpi") {
    const value = config.value as string | number | undefined;
    const label = config.label as string | undefined;
    return (
      <div className="flex h-full flex-col items-center justify-center text-center">
        <div className="text-3xl font-bold text-zinc-900">
          {value !== undefined ? String(value) : <span className="text-zinc-300">--</span>}
        </div>
        {label && <div className="mt-1 text-xs font-medium text-zinc-500">{label}</div>}
      </div>
    );
  }

  if (card.card_type === "chart") {
    const chartType = (config.chart_type as string) ?? "bar";
    const series = toSeries(
      config.series,
      [
        { label: "North", value: 124 },
        { label: "South", value: 98 },
        { label: "West", value: 76 },
      ]
    );
    const filtered = series.filter((point) =>
      shouldKeepPoint(point.label, linkedFilter, contextTokens)
    );
    const maxValue = Math.max(...filtered.map((point) => point.value), 1);

    return (
      <div className="flex h-full flex-col gap-3">
        <div className="text-xs font-medium text-zinc-500 capitalize">{chartType} Chart</div>
        {filtered.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-xs text-zinc-400">
            No chart data for current context
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((point) => (
              <div key={point.label}>
                <div className="mb-1 flex items-center justify-between text-[11px] text-zinc-500">
                  <span>{point.label}</span>
                  <span>{point.value}</span>
                </div>
                <div className="h-2 rounded-full bg-zinc-100">
                  <div
                    className="h-2 rounded-full bg-violet-500 transition-all"
                    style={{ width: `${(point.value / maxValue) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
        <ContextChipRow contextValues={contextValues} linkedFilter={linkedFilter} />
      </div>
    );
  }

  if (card.card_type === "grid") {
    const rows = toSeries(
      config.rows,
      [
        { label: "Product Alpha", value: 42 },
        { label: "Product Beta", value: 31 },
        { label: "Product Gamma", value: 18 },
      ]
    );
    const filteredRows = rows.filter((row) =>
      shouldKeepPoint(row.label, linkedFilter, contextTokens)
    );

    return (
      <div className="flex h-full flex-col gap-2">
        <div className="text-xs font-medium text-zinc-500">Grid View</div>
        <div className="space-y-1">
          {filteredRows.map((row) => (
            <button
              key={row.label}
              type="button"
              onClick={() => onEmitLink?.(card.id, row.label, linkTargets)}
              className="flex w-full items-center justify-between rounded border border-zinc-200 px-2 py-1 text-left text-xs text-zinc-700 transition-colors hover:border-violet-200 hover:bg-violet-50"
            >
              <span>{row.label}</span>
              <span className="text-zinc-500">{row.value}</span>
            </button>
          ))}
        </div>
        <ContextChipRow contextValues={contextValues} linkedFilter={linkedFilter} />
      </div>
    );
  }

  if (card.card_type === "button") {
    const buttonText = asString(config.label) ?? card.title ?? "Run Action";
    const action = asString(config.action) ?? "set_filter";
    const targetPageId = asString(config.target_page_id);
    const value = asString(config.value) ?? buttonText;

    return (
      <div className="flex h-full flex-col items-start justify-center gap-3">
        <button
          type="button"
          onClick={() => {
            if (action === "navigate_page" && targetPageId) {
              onNavigatePage?.(targetPageId);
              return;
            }
            if (action === "clear_links") {
              onEmitLink?.(card.id, null, linkTargets);
              return;
            }
            onEmitLink?.(card.id, value, linkTargets);
          }}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-indigo-700"
        >
          {buttonText}
        </button>
        <div className="text-[11px] text-zinc-500">
          Action: {action.replace("_", " ")}
        </div>
        <ContextChipRow contextValues={contextValues} linkedFilter={linkedFilter} />
      </div>
    );
  }

  if (card.card_type === "text") {
    const content = config.content as string | undefined;
    return (
      <div className="h-full overflow-auto space-y-2">
        {content ? (
          <p className="whitespace-pre-wrap text-sm text-zinc-700">{content}</p>
        ) : (
          <p className="text-xs text-zinc-400 italic">No text content</p>
        )}
        <ContextChipRow contextValues={contextValues} linkedFilter={linkedFilter} />
      </div>
    );
  }

  if (card.card_type === "image") {
    const src = config.src as string | undefined;
    const alt = (config.alt as string) ?? "Image";
    return (
      <div className="flex h-full items-center justify-center overflow-hidden rounded">
        {src ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={src} alt={alt} className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="text-xs text-zinc-400">No image URL configured</span>
        )}
      </div>
    );
  }

  if (card.card_type === "filter") {
    const options = asStringArray(config.options);
    const values = options.length > 0 ? options : ["North", "South", "West"];
    return (
      <div className="flex h-full flex-col gap-2">
        <span className="text-xs font-medium text-zinc-500">Filter control</span>
        <div className="flex flex-wrap gap-1">
          {values.map((value) => {
            const selected = linkedFilter === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() =>
                  onEmitLink?.(card.id, selected ? null : value, linkTargets)
                }
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors ${
                  selected
                    ? "bg-cyan-100 text-cyan-700 ring-1 ring-cyan-300"
                    : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
                }`}
              >
                {value}
              </button>
            );
          })}
        </div>
        <ContextChipRow contextValues={contextValues} linkedFilter={linkedFilter} />
      </div>
    );
  }

  return <div className="text-xs text-zinc-400">Unknown card type</div>;
}

function ContextChipRow({
  contextValues,
  linkedFilter,
}: {
  contextValues: Record<string, string[]>;
  linkedFilter: string | null;
}) {
  const activeContext = Object.entries(contextValues).filter(([, values]) => values.length > 0);
  if (activeContext.length === 0 && !linkedFilter) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1 pt-1">
      {activeContext.map(([label, values]) => (
        <span
          key={label}
          className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600"
        >
          {label}: {values.join(", ")}
        </span>
      ))}
      {linkedFilter && (
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-medium text-violet-700">
          Linked: {linkedFilter}
        </span>
      )}
    </div>
  );
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function toSeries(value: unknown, fallback: DataPoint[]): DataPoint[] {
  if (!Array.isArray(value)) {
    return fallback;
  }

  const series = value
    .map((entry) => {
      if (!entry || typeof entry !== "object") {
        return null;
      }

      const maybeLabel = (entry as { label?: unknown }).label;
      const maybeValue = (entry as { value?: unknown }).value;
      if (typeof maybeLabel !== "string" || typeof maybeValue !== "number") {
        return null;
      }

      return {
        label: maybeLabel,
        value: maybeValue,
      };
    })
    .filter((entry): entry is DataPoint => entry !== null);

  return series.length > 0 ? series : fallback;
}

function shouldKeepPoint(
  label: string,
  linkedFilter: string | null,
  contextTokens: string[]
): boolean {
  const normalized = label.toLowerCase();
  const matchesLinkedFilter = linkedFilter
    ? normalized.includes(linkedFilter.toLowerCase())
    : true;
  const matchesContext =
    contextTokens.length === 0
      ? true
      : contextTokens.some((token) => normalized.includes(token));
  return matchesLinkedFilter && matchesContext;
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
      />
    </svg>
  );
}
