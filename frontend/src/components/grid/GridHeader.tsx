"use client";

import type { DimensionItem, Dimension } from "@/lib/api";

export interface ColumnDef {
  key: string;
  label: string;
  dimensionMemberIds: string[];
}

export interface GridHeaderProps {
  dimensions: Dimension[];
  dimensionItems: DimensionItem[];
  columns: ColumnDef[];
  sortColumn: string | null;
  sortDirection: "asc" | "desc";
  onSort: (columnKey: string) => void;
  rowHeaderWidth: number;
}

/**
 * Builds a mapping from dimension id → items belonging to that dimension,
 * preserving order.
 */
function groupItemsByDimension(
  dimensions: Dimension[],
  items: DimensionItem[]
): Map<string, DimensionItem[]> {
  const map = new Map<string, DimensionItem[]>();
  for (const dim of dimensions) {
    map.set(dim.id, []);
  }
  for (const item of items) {
    map.get(item.dimension_id)?.push(item);
  }
  return map;
}

/**
 * For multi-dimension grids renders two header rows:
 *   row 0 — top-level dimension groups (colspan)
 *   row 1 — individual member names
 *
 * For single-dimension grids renders one header row with member names.
 */
export default function GridHeader({
  dimensions,
  dimensionItems,
  columns,
  sortColumn,
  sortDirection,
  onSort,
  rowHeaderWidth,
}: GridHeaderProps) {
  const itemById = new Map(dimensionItems.map((i) => [i.id, i]));
  const itemsByDim = groupItemsByDimension(dimensions, dimensionItems);
  const isMultiDim = dimensions.length > 1;

  if (columns.length === 0) {
    return (
      <thead>
        <tr>
          <th
            style={{ width: rowHeaderWidth }}
            className="sticky left-0 z-20 border-b border-r border-gray-200 bg-gray-100 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
          >
            Line Item
          </th>
        </tr>
      </thead>
    );
  }

  if (!isMultiDim) {
    // Single dimension — one header row
    return (
      <thead>
        <tr>
          <th
            style={{ width: rowHeaderWidth }}
            className="sticky left-0 z-20 border-b border-r border-gray-200 bg-gray-100 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
          >
            Line Item
          </th>
          {columns.map((col) => {
            const isSorted = sortColumn === col.key;
            return (
              <th
                key={col.key}
                onClick={() => onSort(col.key)}
                className="min-w-[100px] cursor-pointer select-none border-b border-r border-gray-200 bg-gray-100 px-2 py-2 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 hover:bg-gray-200"
              >
                <span className="flex items-center justify-end gap-1">
                  {col.label}
                  {isSorted && (
                    <span className="text-blue-500">
                      {sortDirection === "asc" ? "▲" : "▼"}
                    </span>
                  )}
                </span>
              </th>
            );
          })}
        </tr>
      </thead>
    );
  }

  // Multi-dimension — build group headers for first dimension
  // Columns are cross-products; figure out spans by the first dimension member
  const firstDimId = dimensions[0].id;
  const firstDimItems = itemsByDim.get(firstDimId) ?? [];
  const firstDimItemIds = new Set(firstDimItems.map((i) => i.id));

  // Count how many columns fall under each first-dim member
  const groupSpans: { id: string; label: string; span: number }[] = [];
  for (const col of columns) {
    const topId = col.dimensionMemberIds.find((id) => firstDimItemIds.has(id));
    if (!topId) continue;
    const last = groupSpans[groupSpans.length - 1];
    if (last && last.id === topId) {
      last.span++;
    } else {
      groupSpans.push({
        id: topId,
        label: itemById.get(topId)?.name ?? topId,
        span: 1,
      });
    }
  }

  return (
    <thead>
      {/* Row 0: dimension groups */}
      <tr>
        <th
          rowSpan={2}
          style={{ width: rowHeaderWidth }}
          className="sticky left-0 z-20 border-b border-r border-gray-200 bg-gray-100 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
        >
          Line Item
        </th>
        {groupSpans.map((g) => (
          <th
            key={g.id}
            colSpan={g.span}
            className="border-b border-r border-gray-200 bg-gray-200 px-2 py-1 text-center text-xs font-bold uppercase tracking-wide text-gray-600"
          >
            {g.label}
          </th>
        ))}
      </tr>
      {/* Row 1: individual member names */}
      <tr>
        {columns.map((col) => {
          const isSorted = sortColumn === col.key;
          // Label is the last dimension member name
          const lastId = col.dimensionMemberIds[col.dimensionMemberIds.length - 1];
          const label = itemById.get(lastId)?.name ?? col.label;
          return (
            <th
              key={col.key}
              onClick={() => onSort(col.key)}
              className="min-w-[100px] cursor-pointer select-none border-b border-r border-gray-200 bg-gray-100 px-2 py-2 text-right text-xs font-semibold tracking-wide text-gray-500 hover:bg-gray-200"
            >
              <span className="flex items-center justify-end gap-1">
                {label}
                {isSorted && (
                  <span className="text-blue-500">
                    {sortDirection === "asc" ? "▲" : "▼"}
                  </span>
                )}
              </span>
            </th>
          );
        })}
      </tr>
    </thead>
  );
}
