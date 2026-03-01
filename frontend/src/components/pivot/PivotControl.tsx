"use client";

import { useCallback, useEffect, useState } from "react";
import type { Dimension, DimensionId, PivotConfig } from "@/lib/pivot-utils";
import DimensionChip from "./DimensionChip";
import DropZone, { type ZoneName } from "./DropZone";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PivotControlProps {
  /** All dimensions available in the current model/module. */
  allDimensions: Dimension[];
  /** Initial pivot state. Defaults to all dimensions in "available". */
  initialPivot?: PivotConfig;
  /** Called whenever the pivot config changes. */
  onChange: (pivot: PivotConfig) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Return all dimensions in the given zone based on the pivot config. */
function dimensionsForZone(
  zone: ZoneName,
  pivot: PivotConfig,
  allDimensions: Dimension[]
): Dimension[] {
  const ids = pivot[zone];
  return ids.flatMap((id) => {
    const found = allDimensions.find((d) => d.id === id);
    return found ? [found] : [];
  });
}

/** Return dimensions not currently placed in any zone. */
function availableDimensions(
  pivot: PivotConfig,
  allDimensions: Dimension[]
): Dimension[] {
  const placed = new Set([...pivot.rows, ...pivot.columns, ...pivot.pages]);
  return allDimensions.filter((d) => !placed.has(d.id));
}

/** Remove a dimension ID from whichever zone it is currently in. */
function removeDimensionFromPivot(
  id: DimensionId,
  pivot: PivotConfig
): PivotConfig {
  return {
    rows: pivot.rows.filter((x) => x !== id),
    columns: pivot.columns.filter((x) => x !== id),
    pages: pivot.pages.filter((x) => x !== id),
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PivotControl({
  allDimensions,
  initialPivot,
  onChange,
}: PivotControlProps) {
  const [pivot, setPivot] = useState<PivotConfig>(
    initialPivot ?? { rows: [], columns: [], pages: [] }
  );

  // Keep parent in sync whenever pivot changes.
  useEffect(() => {
    onChange(pivot);
    // onChange identity is not guaranteed stable — only run on pivot changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pivot]);

  // -------------------------------------------------------------------------
  // Drag state — track which dim is being dragged for visual feedback only.
  // The actual data transfer happens via the HTML5 dataTransfer API.
  // -------------------------------------------------------------------------
  const [draggingId, setDraggingId] = useState<DimensionId | null>(null);

  const handleDragStart = useCallback(
    (dimensionId: DimensionId, _sourceZone: ZoneName | "available") => {
      setDraggingId(dimensionId);
    },
    []
  );

  // -------------------------------------------------------------------------
  // Drop handler — called by DropZone components
  // -------------------------------------------------------------------------
  const handleDropOnZone = useCallback(
    (targetZone: ZoneName, dimensionId: DimensionId) => {
      setDraggingId(null);
      setPivot((prev) => {
        // Remove from whatever zone it was in (or available).
        const cleaned = removeDimensionFromPivot(dimensionId, prev);
        // Add to target zone (append at end).
        return {
          ...cleaned,
          [targetZone]: [...cleaned[targetZone], dimensionId],
        };
      });
    },
    []
  );

  // -------------------------------------------------------------------------
  // Drop handler for the "Available" area — return chip to unplaced pool
  // -------------------------------------------------------------------------
  const [isOverAvailable, setIsOverAvailable] = useState(false);

  function handleAvailableDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setIsOverAvailable(true);
  }

  function handleAvailableDragLeave(e: React.DragEvent<HTMLDivElement>) {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setIsOverAvailable(false);
    }
  }

  function handleAvailableDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsOverAvailable(false);
    const raw = e.dataTransfer.getData("application/x-dimension");
    if (!raw) return;
    try {
      const { id } = JSON.parse(raw) as { id: string };
      setPivot((prev) => removeDimensionFromPivot(id, prev));
    } catch {
      // Malformed payload — ignore.
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const available = availableDimensions(pivot, allDimensions);
  const zones: ZoneName[] = ["rows", "columns", "pages"];

  return (
    <div
      className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
      aria-label="Pivot control"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-800">Pivot Dimensions</h2>
        <span className="text-xs text-zinc-400">
          Drag dimensions to change layout
        </span>
      </div>

      {/* Available dimensions pool */}
      <div className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Available
        </span>
        <div
          role="region"
          aria-label="Available dimensions"
          onDragOver={handleAvailableDragOver}
          onDragLeave={handleAvailableDragLeave}
          onDrop={handleAvailableDrop}
          className={[
            "min-h-[48px] w-full rounded-lg border-2 border-dashed px-3 py-2",
            "flex flex-wrap gap-2 items-center transition-all duration-150",
            isOverAvailable
              ? "border-zinc-400 bg-zinc-100 ring-2 ring-zinc-300"
              : "border-zinc-200 bg-zinc-50/60",
          ].join(" ")}
        >
          {available.length === 0 ? (
            <span className="pointer-events-none text-xs italic text-zinc-400">
              All dimensions placed
            </span>
          ) : (
            available.map((dim) => (
              <DimensionChip
                key={dim.id}
                dimension={dim}
                zone="available"
                onDragStart={handleDragStart}
              />
            ))
          )}
        </div>
      </div>

      {/* Divider */}
      <hr className="border-zinc-100" />

      {/* Three drop zones */}
      <div className="flex flex-col gap-4">
        {zones.map((zone) => (
          <DropZone
            key={zone}
            zone={zone}
            dimensions={dimensionsForZone(zone, pivot, allDimensions)}
            onDragStart={handleDragStart}
            onDrop={(dimensionId) => handleDropOnZone(zone, dimensionId)}
          />
        ))}
      </div>

      {/* Subtle drag indicator when dragging */}
      {draggingId !== null && (
        <p
          aria-live="polite"
          className="text-center text-xs text-zinc-400 italic"
        >
          Dragging{" "}
          <strong className="text-zinc-600">
            {allDimensions.find((d) => d.id === draggingId)?.name ?? draggingId}
          </strong>{" "}
          — drop into a zone
        </p>
      )}
    </div>
  );
}
