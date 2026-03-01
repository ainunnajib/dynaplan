"use client";

import { useCallback, useEffect, useState } from "react";
import type {
  Dimension,
  DimensionId,
  DimensionMember,
  MemberId,
} from "@/lib/pivot-utils";
import FilterDropdown from "./FilterDropdown";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Map of dimensionId -> array of selected member IDs. */
export type FilterState = Record<DimensionId, MemberId[]>;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FilterPanelProps {
  /**
   * The dimensions placed on the "pages" axis — these are the context
   * filter dimensions rendered in this panel.
   */
  pageDimensions: Dimension[];
  /**
   * Map from dimensionId -> ordered members for that dimension.
   * Determines which checkboxes appear in each dropdown.
   */
  dimensionItems: Record<DimensionId, DimensionMember[]>;
  /**
   * Initial filter selections.  Defaults to all members selected
   * for each dimension if not provided.
   */
  initialFilters?: FilterState;
  /** Called whenever any filter selection changes. */
  onChange: (filters: FilterState) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build an initial state that selects all members for each page dimension. */
function buildDefaultFilters(
  pageDimensions: Dimension[],
  dimensionItems: Record<DimensionId, DimensionMember[]>
): FilterState {
  const state: FilterState = {};
  for (const dim of pageDimensions) {
    const items = dimensionItems[dim.id] ?? [];
    state[dim.id] = items.map((m) => m.id);
  }
  return state;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FilterPanel({
  pageDimensions,
  dimensionItems,
  initialFilters,
  onChange,
}: FilterPanelProps) {
  const [filters, setFilters] = useState<FilterState>(() => {
    if (initialFilters) return initialFilters;
    return buildDefaultFilters(pageDimensions, dimensionItems);
  });

  // When page dimensions change (e.g. user adds a new one to the pages axis),
  // ensure newly introduced dimensions start with all members selected.
  useEffect(() => {
    setFilters((prev) => {
      const next = { ...prev };
      for (const dim of pageDimensions) {
        if (!(dim.id in next)) {
          const items = dimensionItems[dim.id] ?? [];
          next[dim.id] = items.map((m) => m.id);
        }
      }
      // Remove stale keys for dimensions no longer on pages.
      const pageIds = new Set(pageDimensions.map((d) => d.id));
      for (const key of Object.keys(next)) {
        if (!pageIds.has(key)) delete next[key];
      }
      return next;
    });
  }, [pageDimensions, dimensionItems]);

  // Propagate to parent.
  useEffect(() => {
    onChange(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const handleDimensionChange = useCallback(
    (dimensionId: DimensionId, selectedIds: MemberId[]) => {
      setFilters((prev) => ({ ...prev, [dimensionId]: selectedIds }));
    },
    []
  );

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (pageDimensions.length === 0) {
    return (
      <div className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-800">Filters</h2>
        </div>
        <p className="text-xs text-zinc-400 italic">
          Move dimensions to the &ldquo;Pages&rdquo; zone in the pivot panel to
          enable filters.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-800">Filters</h2>
        <button
          type="button"
          onClick={() => {
            const reset = buildDefaultFilters(pageDimensions, dimensionItems);
            setFilters(reset);
          }}
          className="text-xs text-zinc-400 hover:text-zinc-600 focus:outline-none focus-visible:underline transition-colors"
          aria-label="Reset all filters to show all members"
        >
          Reset all
        </button>
      </div>

      {/* One FilterDropdown per page dimension */}
      <div className="flex flex-col gap-2">
        {pageDimensions.map((dim) => {
          const members = dimensionItems[dim.id] ?? [];
          const selected = filters[dim.id] ?? [];
          return (
            <FilterDropdown
              key={dim.id}
              label={dim.name}
              members={members}
              selectedIds={selected}
              onChange={(ids) => handleDimensionChange(dim.id, ids)}
            />
          );
        })}
      </div>

      {/* Global summary */}
      <div className="border-t border-zinc-100 pt-2 text-right">
        <span className="text-xs text-zinc-400">
          {pageDimensions.length} dimension
          {pageDimensions.length !== 1 ? "s" : ""} filtered
        </span>
      </div>
    </div>
  );
}
