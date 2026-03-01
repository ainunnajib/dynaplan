"use client";

import { useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CardType = "grid" | "chart" | "kpi" | "text" | "image" | "filter";

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
  onDelete?: (cardId: string) => void;
  onUpdate?: (cardId: string, patch: Partial<UXCardData>) => void;
}

// ---------------------------------------------------------------------------
// Label / color maps
// ---------------------------------------------------------------------------

const CARD_TYPE_LABELS: Record<CardType, string> = {
  grid: "Grid",
  chart: "Chart",
  kpi: "KPI",
  text: "Text",
  image: "Image",
  filter: "Filter",
};

const CARD_TYPE_COLORS: Record<CardType, string> = {
  grid: "bg-blue-50 text-blue-600",
  chart: "bg-purple-50 text-purple-600",
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
  onDelete,
  onUpdate,
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
        <CardBody card={card} />
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

function CardBody({ card }: { card: UXCardData }) {
  const config = card.config ?? {};

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
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <div className="text-xs font-medium text-zinc-500 capitalize">{chartType} Chart</div>
        <div className="text-xs text-zinc-400">Connect a module to display data</div>
      </div>
    );
  }

  if (card.card_type === "grid") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
        <div className="text-xs font-medium text-zinc-500">Grid View</div>
        <div className="text-xs text-zinc-400">Select a module to display</div>
      </div>
    );
  }

  if (card.card_type === "text") {
    const content = config.content as string | undefined;
    return (
      <div className="h-full overflow-auto">
        {content ? (
          <p className="whitespace-pre-wrap text-sm text-zinc-700">{content}</p>
        ) : (
          <p className="text-xs text-zinc-400 italic">No text content</p>
        )}
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
    return (
      <div className="flex h-full items-center justify-center">
        <span className="text-xs text-zinc-400">Filter control</span>
      </div>
    );
  }

  return <div className="text-xs text-zinc-400">Unknown card type</div>;
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
