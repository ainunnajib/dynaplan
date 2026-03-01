"use client";

import { useMemo } from "react";

// Deterministic color generation — same logic as PresenceBar for consistency
const CURSOR_COLORS = [
  { bg: "bg-blue-200", border: "border-blue-500", text: "text-blue-700" },
  { bg: "bg-green-200", border: "border-green-500", text: "text-green-700" },
  { bg: "bg-purple-200", border: "border-purple-500", text: "text-purple-700" },
  { bg: "bg-orange-200", border: "border-orange-500", text: "text-orange-700" },
  { bg: "bg-pink-200", border: "border-pink-500", text: "text-pink-700" },
  { bg: "bg-teal-200", border: "border-teal-500", text: "text-teal-700" },
  { bg: "bg-red-200", border: "border-red-500", text: "text-red-700" },
  { bg: "bg-indigo-200", border: "border-indigo-500", text: "text-indigo-700" },
];

function getColorIndexForUser(userId: string): number {
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = (hash * 31 + userId.charCodeAt(i)) >>> 0;
  }
  return hash % CURSOR_COLORS.length;
}

export interface RemoteCursor {
  userId: string;
  userFullName: string | null;
  cellRef: string | null;
}

interface CursorOverlayProps {
  /** Remote cursors from other users (not the current user). */
  remoteCursors: RemoteCursor[];
  /**
   * A function that maps a cellRef (e.g. "R1C3") to a DOMRect or null
   * indicating the position of the cell in the current viewport.
   * If null/undefined, an absolute fallback is used.
   */
  getCellRect?: (cellRef: string) => DOMRect | null;
}

/**
 * CursorOverlay renders colored cell highlight indicators for other users'
 * cursor positions. Each user gets a consistent color derived from their
 * user ID.
 *
 * When getCellRect is provided, overlays are positioned over the actual cell.
 * Otherwise they display as a floating list of indicators.
 */
export function CursorOverlay({
  remoteCursors,
  getCellRect,
}: CursorOverlayProps) {
  const activeCursors = useMemo(
    () => remoteCursors.filter((c) => c.cellRef !== null),
    [remoteCursors]
  );

  if (activeCursors.length === 0) return null;

  return (
    <>
      {activeCursors.map((cursor) => {
        const colorIdx = getColorIndexForUser(cursor.userId);
        const colors = CURSOR_COLORS[colorIdx];
        const displayName = cursor.userFullName ?? cursor.userId.slice(0, 8);

        // If we have a getCellRect function, try to overlay the cell
        if (getCellRect && cursor.cellRef) {
          const rect = getCellRect(cursor.cellRef);
          if (rect) {
            return (
              <CellHighlight
                key={cursor.userId}
                rect={rect}
                colors={colors}
                displayName={displayName}
                cellRef={cursor.cellRef}
              />
            );
          }
        }

        // Fallback: show as a floating badge
        return (
          <FloatingCursorBadge
            key={cursor.userId}
            colors={colors}
            displayName={displayName}
            cellRef={cursor.cellRef ?? ""}
          />
        );
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Internal sub-components
// ---------------------------------------------------------------------------

interface CellHighlightProps {
  rect: DOMRect;
  colors: (typeof CURSOR_COLORS)[number];
  displayName: string;
  cellRef: string;
}

function CellHighlight({ rect, colors, displayName, cellRef }: CellHighlightProps) {
  return (
    <div
      className={`
        pointer-events-none fixed z-40
        border-2 ${colors.border} ${colors.bg} opacity-40
      `}
      style={{
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      }}
      aria-hidden="true"
    >
      {/* Label at top-right of the highlighted cell */}
      <span
        className={`
          absolute -top-5 right-0
          text-xs px-1 py-0.5 rounded
          ${colors.bg} ${colors.text} border ${colors.border}
          opacity-100 pointer-events-none whitespace-nowrap
        `}
      >
        {displayName}
      </span>
    </div>
  );
}

interface FloatingCursorBadgeProps {
  colors: (typeof CURSOR_COLORS)[number];
  displayName: string;
  cellRef: string;
}

function FloatingCursorBadge({
  colors,
  displayName,
  cellRef,
}: FloatingCursorBadgeProps) {
  return (
    <div
      className={`
        inline-flex items-center gap-1
        text-xs px-2 py-0.5 rounded-full
        border ${colors.border} ${colors.bg} ${colors.text}
      `}
      title={`${displayName} is at ${cellRef}`}
    >
      <span className="font-medium">{displayName}</span>
      <span className="opacity-70">@ {cellRef}</span>
    </div>
  );
}
