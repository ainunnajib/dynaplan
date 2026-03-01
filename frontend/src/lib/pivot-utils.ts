/**
 * pivot-utils.ts
 *
 * Utility functions for building grid layouts from pivot configuration and
 * dimension data. Used by the grid view and pivot control components.
 */

// ---------------------------------------------------------------------------
// Shared types (inlined here so this file has zero external deps)
// ---------------------------------------------------------------------------

export type DimensionId = string;
export type MemberId = string;

export interface DimensionMember {
  id: MemberId;
  name: string;
  parentId: MemberId | null;
  /** Depth in the hierarchy tree (0 = root). */
  depth: number;
}

export interface Dimension {
  id: DimensionId;
  name: string;
  /** "time" | "version" | "custom" | "numbered" */
  type: "time" | "version" | "custom" | "numbered";
}

export interface PivotConfig {
  rows: DimensionId[];
  columns: DimensionId[];
  pages: DimensionId[];
}

export interface GridHeader {
  /** The ordered member IDs that compose this header cell. */
  memberIds: MemberId[];
  /** Human-readable labels for each member ID (same order). */
  labels: string[];
  /** The canonical dimension key (sorted pipe-joined) for backend lookups. */
  dimensionKey: string;
}

export interface GridLayout {
  rowHeaders: GridHeader[];
  columnHeaders: GridHeader[];
}

// ---------------------------------------------------------------------------
// buildDimensionKey
// ---------------------------------------------------------------------------

/**
 * Sort the given member IDs and join with "|" — matching the backend's
 * cell storage convention (sparse table uses sorted pipe-separated keys).
 *
 * @example
 * buildDimensionKey(["Q2-2026", "Budget", "EMEA"])
 * // => "Budget|EMEA|Q2-2026"
 */
export function buildDimensionKey(memberIds: MemberId[]): string {
  return [...memberIds].sort().join("|");
}

// ---------------------------------------------------------------------------
// crossProduct
// ---------------------------------------------------------------------------

/**
 * Compute the Cartesian product of an array of arrays.
 *
 * @example
 * crossProduct([["A", "B"], ["1", "2"]])
 * // => [["A","1"], ["A","2"], ["B","1"], ["B","2"]]
 */
export function crossProduct<T>(arrays: T[][]): T[][] {
  if (arrays.length === 0) return [[]];

  return arrays.reduce<T[][]>(
    (acc, curr) => {
      const result: T[][] = [];
      for (const existing of acc) {
        for (const item of curr) {
          result.push([...existing, item]);
        }
      }
      return result;
    },
    [[]]
  );
}

// ---------------------------------------------------------------------------
// buildGridLayout
// ---------------------------------------------------------------------------

/**
 * Given the pivot configuration (which dimensions are on rows vs. columns),
 * the dimension metadata map, and the per-dimension member arrays, compute
 * the ordered row headers and column headers that describe the grid structure.
 *
 * Only members that appear in `dimensionItems` are used. Dimensions listed in
 * `pivot.pages` are context-filter dimensions and do NOT contribute row/column
 * headers — they are handled by the FilterPanel instead.
 *
 * @param pivot          - Current pivot config (rows / columns / pages).
 * @param dimensions     - Map of dimensionId -> Dimension metadata.
 * @param dimensionItems - Map of dimensionId -> ordered array of members.
 * @returns              - { rowHeaders, columnHeaders } for the grid.
 */
export function buildGridLayout(
  pivot: PivotConfig,
  dimensions: Record<DimensionId, Dimension>,
  dimensionItems: Record<DimensionId, DimensionMember[]>
): GridLayout {
  const buildHeaders = (dimIds: DimensionId[]): GridHeader[] => {
    // For each dimension ID in the axis, collect its member array.
    // If a dimension is missing from dimensionItems we skip it gracefully.
    const memberArrays: DimensionMember[][] = dimIds
      .map((id) => dimensionItems[id] ?? [])
      .filter((arr) => arr.length > 0);

    if (memberArrays.length === 0) return [];

    // Build the cross product of members across all dimensions on this axis.
    const combos = crossProduct(memberArrays);

    return combos.map((combo) => {
      const memberIds = combo.map((m) => m.id);
      const labels = combo.map((m) => m.name);
      return {
        memberIds,
        labels,
        dimensionKey: buildDimensionKey(memberIds),
      };
    });
  };

  return {
    rowHeaders: buildHeaders(pivot.rows),
    columnHeaders: buildHeaders(pivot.columns),
  };
}
