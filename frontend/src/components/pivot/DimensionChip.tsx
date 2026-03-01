"use client";

import { type DragEvent } from "react";
import type { Dimension } from "@/lib/pivot-utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DimensionChipProps {
  dimension: Dimension;
  /** Zone the chip currently lives in, or "available" if not yet placed. */
  zone: "rows" | "columns" | "pages" | "available";
  onDragStart: (dimensionId: string, sourceZone: DimensionChipProps["zone"]) => void;
}

// ---------------------------------------------------------------------------
// Dimension type icon helpers
// ---------------------------------------------------------------------------

/** Minimal inline SVG icons — no external icon library required. */
function TimeIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-3 w-3 shrink-0"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <circle cx="8" cy="8" r="6.5" />
      <path d="M8 4.5V8l2.5 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function VersionIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-3 w-3 shrink-0"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path
        d="M4 4h8M4 8h5M4 12h3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11 10l2 2-2 2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CustomIcon() {
  return (
    <svg
      aria-hidden="true"
      className="h-3 w-3 shrink-0"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <rect x="2.5" y="2.5" width="5" height="5" rx="0.5" />
      <rect x="8.5" y="2.5" width="5" height="5" rx="0.5" />
      <rect x="2.5" y="8.5" width="5" height="5" rx="0.5" />
      <rect x="8.5" y="8.5" width="5" height="5" rx="0.5" />
    </svg>
  );
}

function DimensionTypeIcon({ type }: { type: Dimension["type"] }) {
  if (type === "time") return <TimeIcon />;
  if (type === "version") return <VersionIcon />;
  return <CustomIcon />;
}

// ---------------------------------------------------------------------------
// Zone colour accents
// ---------------------------------------------------------------------------

const ZONE_STYLES: Record<DimensionChipProps["zone"], string> = {
  rows: "bg-blue-50 border-blue-200 text-blue-800 hover:border-blue-400",
  columns: "bg-violet-50 border-violet-200 text-violet-800 hover:border-violet-400",
  pages: "bg-amber-50 border-amber-200 text-amber-800 hover:border-amber-400",
  available: "bg-zinc-50 border-zinc-200 text-zinc-700 hover:border-zinc-400",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DimensionChip({
  dimension,
  zone,
  onDragStart,
}: DimensionChipProps) {
  function handleDragStart(e: DragEvent<HTMLDivElement>) {
    // Store the dimension ID and source zone in the drag transfer payload.
    e.dataTransfer.setData(
      "application/x-dimension",
      JSON.stringify({ id: dimension.id, sourceZone: zone })
    );
    e.dataTransfer.effectAllowed = "move";
    onDragStart(dimension.id, zone);
  }

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      role="button"
      aria-label={`Drag dimension ${dimension.name}`}
      tabIndex={0}
      className={[
        "inline-flex cursor-grab items-center gap-1.5 rounded-full border px-2.5 py-1",
        "text-xs font-medium select-none transition-all duration-150",
        "active:cursor-grabbing active:opacity-50 active:scale-95",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
        ZONE_STYLES[zone],
      ].join(" ")}
    >
      <DimensionTypeIcon type={dimension.type} />
      <span>{dimension.name}</span>
    </div>
  );
}
