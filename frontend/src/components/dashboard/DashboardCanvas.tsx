"use client";

import { useState, useRef, useCallback } from "react";
import { updateWidget } from "@/lib/api";
import type { DashboardWithWidgets, DashboardWidget } from "@/lib/api";
import WidgetContainer from "./WidgetContainer";

const GRID_COLS = 12;
const COL_WIDTH_PX = 80; // approximate per-column width
const ROW_HEIGHT_PX = 80;
const GAP_PX = 8;

interface DragState {
  widgetId: string;
  startX: number;
  startY: number;
  origPosX: number;
  origPosY: number;
}

interface ResizeState {
  widgetId: string;
  startX: number;
  startY: number;
  origWidth: number;
  origHeight: number;
}

interface Props {
  dashboard: DashboardWithWidgets;
  isEditMode: boolean;
  onDashboardChange: (updater: (prev: DashboardWithWidgets | null) => DashboardWithWidgets | null) => void;
}

export default function DashboardCanvas({ dashboard, isEditMode, onDashboardChange }: Props) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [resizeState, setResizeState] = useState<ResizeState | null>(null);
  const [saving, setSaving] = useState<string | null>(null); // widgetId being saved

  const colWidth = COL_WIDTH_PX + GAP_PX;
  const rowHeight = ROW_HEIGHT_PX + GAP_PX;
  const canvasMinWidth = GRID_COLS * COL_WIDTH_PX + (GRID_COLS + 1) * GAP_PX;

  const getWidgetStyle = (widget: DashboardWidget) => {
    return {
      gridColumn: `${widget.position_x + 1} / span ${widget.width}`,
      gridRow: `${widget.position_y + 1} / span ${widget.height}`,
    };
  };

  const saveWidget = useCallback(
    async (widgetId: string, patch: Partial<DashboardWidget>) => {
      setSaving(widgetId);
      try {
        const sanitized: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(patch)) {
          if (v !== undefined) sanitized[k] = v === null ? undefined : v;
        }
        const updated = await updateWidget(widgetId, sanitized as Parameters<typeof updateWidget>[1]);
        onDashboardChange((prev) =>
          prev
            ? {
                ...prev,
                widgets: prev.widgets.map((w) =>
                  w.id === widgetId ? { ...w, ...updated } : w
                ),
              }
            : prev
        );
      } catch {
        // silently fail — widget stays at its optimistic position
      } finally {
        setSaving(null);
      }
    },
    [onDashboardChange]
  );

  function handleDragStart(
    e: React.MouseEvent,
    widget: DashboardWidget
  ) {
    if (!isEditMode) return;
    e.preventDefault();
    setDragState({
      widgetId: widget.id,
      startX: e.clientX,
      startY: e.clientY,
      origPosX: widget.position_x,
      origPosY: widget.position_y,
    });
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!isEditMode) return;

    if (dragState) {
      const dx = e.clientX - dragState.startX;
      const dy = e.clientY - dragState.startY;
      const newCol = Math.max(0, Math.min(GRID_COLS - 1, dragState.origPosX + Math.round(dx / colWidth)));
      const newRow = Math.max(0, dragState.origPosY + Math.round(dy / rowHeight));

      onDashboardChange((prev) =>
        prev
          ? {
              ...prev,
              widgets: prev.widgets.map((w) =>
                w.id === dragState.widgetId
                  ? { ...w, position_x: newCol, position_y: newRow }
                  : w
              ),
            }
          : prev
      );
    }

    if (resizeState) {
      const dx = e.clientX - resizeState.startX;
      const dy = e.clientY - resizeState.startY;
      const newWidth = Math.max(1, Math.min(GRID_COLS, resizeState.origWidth + Math.round(dx / colWidth)));
      const newHeight = Math.max(1, resizeState.origHeight + Math.round(dy / rowHeight));

      onDashboardChange((prev) =>
        prev
          ? {
              ...prev,
              widgets: prev.widgets.map((w) =>
                w.id === resizeState.widgetId
                  ? { ...w, width: newWidth, height: newHeight }
                  : w
              ),
            }
          : prev
      );
    }
  }

  function handleMouseUp() {
    if (dragState) {
      const widget = dashboard.widgets.find((w) => w.id === dragState.widgetId);
      if (widget) {
        saveWidget(widget.id, {
          position_x: widget.position_x,
          position_y: widget.position_y,
        });
      }
      setDragState(null);
    }

    if (resizeState) {
      const widget = dashboard.widgets.find((w) => w.id === resizeState.widgetId);
      if (widget) {
        saveWidget(widget.id, {
          width: widget.width,
          height: widget.height,
        });
      }
      setResizeState(null);
    }
  }

  function handleResizeStart(e: React.MouseEvent, widget: DashboardWidget) {
    if (!isEditMode) return;
    e.preventDefault();
    e.stopPropagation();
    setResizeState({
      widgetId: widget.id,
      startX: e.clientX,
      startY: e.clientY,
      origWidth: widget.width,
      origHeight: widget.height,
    });
  }

  function handleDeleteWidget(widgetId: string) {
    onDashboardChange((prev) =>
      prev
        ? { ...prev, widgets: prev.widgets.filter((w) => w.id !== widgetId) }
        : prev
    );
  }

  if (dashboard.widgets.length === 0 && !isEditMode) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-zinc-300 bg-white py-24 text-center">
        <GridIcon className="h-12 w-12 text-zinc-300" />
        <h3 className="mt-4 text-sm font-medium text-zinc-600">Dashboard is empty</h3>
        <p className="mt-1 text-xs text-zinc-400 max-w-xs">
          Click &quot;Edit Layout&quot; then &quot;Add Widget&quot; to start building your dashboard.
        </p>
      </div>
    );
  }

  // Compute total rows needed
  const maxRow = dashboard.widgets.reduce(
    (max, w) => Math.max(max, w.position_y + w.height),
    4
  );

  return (
    <div
      ref={canvasRef}
      className={`relative rounded-xl bg-white shadow-sm ${isEditMode ? "ring-2 ring-violet-200" : ""}`}
      style={{
        minHeight: `${maxRow * rowHeight + GAP_PX * 2}px`,
        minWidth: `${canvasMinWidth}px`,
      }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Grid overlay in edit mode */}
      {isEditMode && (
        <div
          className="pointer-events-none absolute inset-0 rounded-xl"
          style={{
            backgroundImage:
              "linear-gradient(to right, rgb(139 92 246 / 0.06) 1px, transparent 1px), linear-gradient(to bottom, rgb(139 92 246 / 0.06) 1px, transparent 1px)",
            backgroundSize: `${colWidth}px ${rowHeight}px`,
            backgroundPosition: `${GAP_PX}px ${GAP_PX}px`,
          }}
        />
      )}

      {/* Widgets rendered as CSS Grid */}
      <div
        className="relative p-2"
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${GRID_COLS}, ${COL_WIDTH_PX}px)`,
          gridAutoRows: `${ROW_HEIGHT_PX}px`,
          gap: `${GAP_PX}px`,
        }}
      >
        {dashboard.widgets.map((widget) => (
          <div
            key={widget.id}
            style={getWidgetStyle(widget)}
            className={`relative ${dragState?.widgetId === widget.id ? "z-20 opacity-90 shadow-2xl" : "z-10"}`}
          >
            <WidgetContainer
              widget={widget}
              isEditMode={isEditMode}
              isSaving={saving === widget.id}
              onDragStart={(e) => handleDragStart(e, widget)}
              onResizeStart={(e) => handleResizeStart(e, widget)}
              onDelete={() => handleDeleteWidget(widget.id)}
              onWidgetUpdate={(updated) => {
                onDashboardChange((prev) =>
                  prev
                    ? {
                        ...prev,
                        widgets: prev.widgets.map((w) =>
                          w.id === widget.id ? { ...w, ...updated } : w
                        ),
                      }
                    : prev
                );
              }}
            />
          </div>
        ))}
      </div>

      {/* Drop area hint in edit mode when canvas is empty or partially filled */}
      {isEditMode && dashboard.widgets.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <p className="text-sm text-zinc-400">Click &quot;Add Widget&quot; to place widgets on the canvas</p>
        </div>
      )}
    </div>
  );
}

function GridIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 0 1-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0 1 12 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5" />
    </svg>
  );
}
