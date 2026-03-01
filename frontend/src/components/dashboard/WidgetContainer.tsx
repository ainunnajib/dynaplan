"use client";

import { useState } from "react";
import { deleteWidget, updateWidget } from "@/lib/api";
import type { DashboardWidget, WidgetType } from "@/lib/api";

interface Props {
  widget: DashboardWidget;
  isEditMode: boolean;
  isSaving: boolean;
  onDragStart: (e: React.MouseEvent) => void;
  onResizeStart: (e: React.MouseEvent) => void;
  onDelete: () => void;
  onWidgetUpdate: (updated: Partial<DashboardWidget>) => void;
}

const WIDGET_TYPE_LABELS: Record<WidgetType, string> = {
  grid: "Grid",
  chart: "Chart",
  kpi_card: "KPI Card",
  text: "Text",
  image: "Image",
};

const WIDGET_TYPE_COLORS: Record<WidgetType, string> = {
  grid: "bg-blue-50 text-blue-600",
  chart: "bg-purple-50 text-purple-600",
  kpi_card: "bg-emerald-50 text-emerald-600",
  text: "bg-amber-50 text-amber-600",
  image: "bg-pink-50 text-pink-600",
};

export default function WidgetContainer({
  widget,
  isEditMode,
  isSaving,
  onDragStart,
  onResizeStart,
  onDelete,
  onWidgetUpdate,
}: Props) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editTitle, setEditTitle] = useState(widget.title ?? "");

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await deleteWidget(widget.id);
      onDelete();
    } catch {
      // swallow — parent still removes optimistically
      onDelete();
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleSaveTitle() {
    const trimmed = editTitle.trim();
    onWidgetUpdate({ title: trimmed || null });
    setIsEditingTitle(false);
    try {
      await updateWidget(widget.id, { title: trimmed || undefined });
    } catch {
      // revert on failure
      onWidgetUpdate({ title: widget.title });
    }
  }

  return (
    <div
      className={`group relative flex h-full w-full flex-col overflow-hidden rounded-lg border bg-white shadow-sm transition-shadow ${
        isEditMode
          ? "border-violet-300 hover:shadow-md cursor-grab active:cursor-grabbing"
          : "border-zinc-200"
      } ${isSaving ? "opacity-75" : ""}`}
      onMouseDown={isEditMode ? onDragStart : undefined}
    >
      {/* Title bar */}
      <div
        className={`flex shrink-0 items-center justify-between gap-2 border-b px-3 py-2 ${
          isEditMode ? "border-violet-100 bg-violet-50/50" : "border-zinc-100 bg-zinc-50"
        }`}
        onMouseDown={(e) => e.stopPropagation()} // prevent drag when interacting with title controls
      >
        <div className="flex items-center gap-2 min-w-0">
          {isEditMode && (
            <GrabIcon className="h-3.5 w-3.5 shrink-0 text-violet-400 cursor-grab" />
          )}
          <span
            className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${WIDGET_TYPE_COLORS[widget.widget_type]}`}
          >
            {WIDGET_TYPE_LABELS[widget.widget_type]}
          </span>

          {isEditingTitle ? (
            <div className="flex items-center gap-1 min-w-0">
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveTitle();
                  if (e.key === "Escape") {
                    setEditTitle(widget.title ?? "");
                    setIsEditingTitle(false);
                  }
                }}
                className="min-w-0 flex-1 rounded border border-violet-300 px-1.5 py-0.5 text-xs text-zinc-900 focus:outline-none focus:ring-1 focus:ring-violet-400"
                autoFocus
                onClick={(e) => e.stopPropagation()}
              />
              <button
                type="button"
                onMouseDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  handleSaveTitle();
                }}
                className="shrink-0 rounded bg-violet-600 px-1.5 py-0.5 text-xs text-white hover:bg-violet-700"
              >
                OK
              </button>
            </div>
          ) : (
            <span
              className={`truncate text-xs font-medium text-zinc-700 ${
                isEditMode ? "cursor-text hover:text-zinc-900" : ""
              }`}
              onDoubleClick={isEditMode ? () => setIsEditingTitle(true) : undefined}
              title={widget.title ?? undefined}
            >
              {widget.title ?? (isEditMode ? <em className="text-zinc-400">Untitled</em> : "")}
            </span>
          )}
        </div>

        {/* Edit-mode action buttons */}
        {isEditMode && !isEditingTitle && (
          <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                setIsEditingTitle(true);
              }}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors"
              title="Rename widget"
            >
              <PencilIcon className="h-3 w-3" />
            </button>
            <button
              type="button"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.stopPropagation();
                setShowDeleteConfirm(true);
              }}
              className="rounded p-1 text-zinc-400 hover:bg-red-50 hover:text-red-500 transition-colors"
              title="Delete widget"
            >
              <TrashIcon className="h-3 w-3" />
            </button>
          </div>
        )}

        {isSaving && (
          <div className="h-3 w-3 animate-spin rounded-full border border-violet-400 border-t-transparent" />
        )}
      </div>

      {/* Widget body */}
      <div
        className="flex-1 overflow-auto p-3"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <WidgetBody widget={widget} />
      </div>

      {/* Resize handle (bottom-right corner) */}
      {isEditMode && (
        <div
          className="absolute bottom-0 right-0 h-5 w-5 cursor-se-resize opacity-0 group-hover:opacity-100 transition-opacity"
          onMouseDown={(e) => {
            e.stopPropagation();
            onResizeStart(e);
          }}
        >
          <ResizeIcon className="h-4 w-4 text-violet-400 absolute bottom-0.5 right-0.5" />
        </div>
      )}

      {/* Delete confirmation overlay */}
      {showDeleteConfirm && (
        <div
          className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-lg bg-white/95 p-4 text-center backdrop-blur-sm"
          onMouseDown={(e) => e.stopPropagation()}
        >
          <ExclamationIcon className="h-6 w-6 text-red-500" />
          <p className="mt-1 text-xs font-semibold text-zinc-800">Delete widget?</p>
          {widget.title && (
            <p className="mt-0.5 text-xs text-zinc-500">&quot;{widget.title}&quot;</p>
          )}
          <div className="mt-3 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              disabled={isDeleting}
              className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {isDeleting ? "..." : "Delete"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Widget body renderers ─────────────────────────────────────────────────────

function WidgetBody({ widget }: { widget: DashboardWidget }) {
  const type = widget.widget_type;
  const config = widget.config ?? {};

  if (type === "kpi_card") {
    return <KpiCardBody config={config} />;
  }
  if (type === "chart") {
    return <ChartBody config={config} />;
  }
  if (type === "grid") {
    return <GridBody config={config} />;
  }
  if (type === "text") {
    return <TextBody config={config} />;
  }
  if (type === "image") {
    return <ImageBody config={config} />;
  }
  return <div className="text-xs text-zinc-400">Unknown widget type</div>;
}

function KpiCardBody({ config }: { config: Record<string, unknown> }) {
  const value = config.value as string | number | undefined;
  const label = config.label as string | undefined;
  const change = config.change as number | undefined;
  const changePositive = typeof change === "number" ? change >= 0 : null;

  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="text-3xl font-bold text-zinc-900">
        {value !== undefined ? String(value) : <span className="text-zinc-300">—</span>}
      </div>
      {label && (
        <div className="mt-1 text-xs font-medium text-zinc-500">{label}</div>
      )}
      {change !== undefined && (
        <div
          className={`mt-2 flex items-center gap-0.5 text-xs font-medium ${
            changePositive ? "text-emerald-600" : "text-red-600"
          }`}
        >
          {changePositive ? (
            <ArrowUpIcon className="h-3 w-3" />
          ) : (
            <ArrowDownIcon className="h-3 w-3" />
          )}
          {Math.abs(change)}%
        </div>
      )}
      {value === undefined && (
        <div className="mt-1 text-xs text-zinc-400">
          Configure data source in widget settings
        </div>
      )}
    </div>
  );
}

function ChartBody({ config }: { config: Record<string, unknown> }) {
  const chartType = (config.chart_type as string | undefined) ?? "bar";

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <ChartIcon className="h-8 w-8 text-zinc-300" />
      <div className="text-xs font-medium text-zinc-500 capitalize">{chartType} Chart</div>
      <div className="text-xs text-zinc-400">
        Connect a module to display data
      </div>
    </div>
  );
}

function GridBody({ config }: { config: Record<string, unknown> }) {
  const moduleId = config.module_id as string | undefined;

  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
      <TableIcon className="h-8 w-8 text-zinc-300" />
      <div className="text-xs font-medium text-zinc-500">Grid View</div>
      {moduleId ? (
        <div className="text-xs text-zinc-400">Module: {moduleId}</div>
      ) : (
        <div className="text-xs text-zinc-400">Select a module to display</div>
      )}
    </div>
  );
}

function TextBody({ config }: { config: Record<string, unknown> }) {
  const content = config.content as string | undefined;

  return (
    <div className="h-full overflow-auto">
      {content ? (
        <p className="whitespace-pre-wrap text-sm text-zinc-700">{content}</p>
      ) : (
        <p className="text-xs text-zinc-400 italic">
          Double-click to edit text content
        </p>
      )}
    </div>
  );
}

function ImageBody({ config }: { config: Record<string, unknown> }) {
  const src = config.src as string | undefined;
  const alt = (config.alt as string | undefined) ?? "Image";

  return (
    <div className="flex h-full items-center justify-center overflow-hidden rounded">
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} className="max-h-full max-w-full object-contain" />
      ) : (
        <div className="flex flex-col items-center gap-2 text-center">
          <ImageIcon className="h-8 w-8 text-zinc-300" />
          <span className="text-xs text-zinc-400">No image URL configured</span>
        </div>
      )}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function GrabIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function ResizeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 19.5 15-15m0 0H8.25m11.25 0v11.25" />
    </svg>
  );
}

function ExclamationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
    </svg>
  );
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5 12 3m0 0 7.5 7.5M12 3v18" />
    </svg>
  );
}

function ArrowDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5 12 21m0 0-7.5-7.5M12 21V3" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
    </svg>
  );
}

function TableIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25" />
    </svg>
  );
}

function ImageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
    </svg>
  );
}
