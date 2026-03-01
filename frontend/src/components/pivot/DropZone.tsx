"use client";

import { type DragEvent, useState } from "react";
import type { Dimension } from "@/lib/pivot-utils";
import DimensionChip from "./DimensionChip";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type ZoneName = "rows" | "columns" | "pages";

interface DropZoneProps {
  zone: ZoneName;
  /** Dimensions currently placed in this zone. */
  dimensions: Dimension[];
  /** Called when a dimension chip is dragged out (drag started). */
  onDragStart: (dimensionId: string, sourceZone: ZoneName | "available") => void;
  /** Called when a dimension is dropped onto this zone. */
  onDrop: (dimensionId: string, sourceZone: ZoneName | "available") => void;
}

// ---------------------------------------------------------------------------
// Zone display metadata
// ---------------------------------------------------------------------------

const ZONE_META: Record<
  ZoneName,
  { label: string; description: string; emptyText: string; colors: string; highlight: string }
> = {
  rows: {
    label: "Rows",
    description: "Dimensions shown as row headers",
    emptyText: "Drop dimension here",
    colors: "border-blue-200 bg-blue-50/50",
    highlight: "border-blue-400 bg-blue-100/60 ring-2 ring-blue-300",
  },
  columns: {
    label: "Columns",
    description: "Dimensions shown as column headers",
    emptyText: "Drop dimension here",
    colors: "border-violet-200 bg-violet-50/50",
    highlight: "border-violet-400 bg-violet-100/60 ring-2 ring-violet-300",
  },
  pages: {
    label: "Pages",
    description: "Context filter dimensions (shown in filter panel)",
    emptyText: "Drop dimension here",
    colors: "border-amber-200 bg-amber-50/50",
    highlight: "border-amber-400 bg-amber-100/60 ring-2 ring-amber-300",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DropZone({
  zone,
  dimensions,
  onDragStart,
  onDrop,
}: DropZoneProps) {
  const [isOver, setIsOver] = useState(false);
  const meta = ZONE_META[zone];

  function handleDragOver(e: DragEvent<HTMLDivElement>) {
    // Must prevent default to allow the drop.
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setIsOver(true);
  }

  function handleDragLeave(e: DragEvent<HTMLDivElement>) {
    // Only clear highlight if the pointer truly left this element, not just
    // moved to a child element.
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setIsOver(false);
    }
  }

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsOver(false);
    const raw = e.dataTransfer.getData("application/x-dimension");
    if (!raw) return;
    try {
      const { id, sourceZone } = JSON.parse(raw) as {
        id: string;
        sourceZone: ZoneName | "available";
      };
      onDrop(id, sourceZone);
    } catch {
      // Malformed payload — ignore.
    }
  }

  function handleDragEnd() {
    setIsOver(false);
  }

  return (
    <div
      className="flex flex-col gap-2"
      onDragEnd={handleDragEnd}
    >
      {/* Zone header */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {meta.label}
        </span>
        <span className="text-xs text-zinc-400" aria-label={meta.description}>
          {meta.description}
        </span>
      </div>

      {/* Drop target */}
      <div
        role="region"
        aria-label={`${meta.label} drop zone`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          "min-h-[52px] w-full rounded-lg border-2 border-dashed px-3 py-2",
          "flex flex-wrap gap-2 items-center transition-all duration-150",
          isOver ? meta.highlight : meta.colors,
        ].join(" ")}
      >
        {dimensions.length === 0 ? (
          <span
            className={[
              "pointer-events-none text-xs italic transition-colors",
              isOver ? "text-zinc-500" : "text-zinc-400",
            ].join(" ")}
          >
            {meta.emptyText}
          </span>
        ) : (
          dimensions.map((dim) => (
            <DimensionChip
              key={dim.id}
              dimension={dim}
              zone={zone}
              onDragStart={onDragStart}
            />
          ))
        )}

        {/* Subtle highlight overlay indicator */}
        {isOver && (
          <span className="pointer-events-none text-xs italic text-zinc-500">
            {dimensions.length > 0 ? "Drop to add" : "Release to place"}
          </span>
        )}
      </div>
    </div>
  );
}
