"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { LineItem, Dimension, DimensionItem, CellValue } from "@/lib/api";
import { useCellData, type DimensionMember } from "@/hooks/useCellData";
import EditableCell from "./EditableCell";
import type { CellFormat } from "./CellFormatting";
import GridHeader, { type ColumnDef } from "./GridHeader";

export interface DataGridProps {
  moduleId: string;
  lineItems: LineItem[];
  dimensions: Dimension[];
  dimensionItems: DimensionItem[];
  /** Initial cells pre-fetched server-side (hydrates the local cache). */
  initialCells?: CellValue[];
}

const ROW_HEIGHT = 36;
const ROW_HEADER_WIDTH = 220;
const COL_WIDTH = 130;

// ── Cartesian product ─────────────────────────────────────────────────────────

function cartesianProduct<T>(arrays: T[][]): T[][] {
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

// ── Column builder ─────────────────────────────────────────────────────────────

function buildColumns(
  lineItems: LineItem[],
  dimensions: Dimension[],
  dimensionItems: DimensionItem[]
): ColumnDef[] {
  const usedDimIds = new Set<string>();
  for (const li of lineItems) {
    for (const dimId of li.applies_to_dimension_ids) {
      usedDimIds.add(dimId);
    }
  }

  const usedDimensions = dimensions.filter((d) => usedDimIds.has(d.id));

  if (usedDimensions.length === 0) {
    return [{ key: "__value__", label: "Value", dimensionMemberIds: [] }];
  }

  const itemsByDim = new Map<string, DimensionItem[]>();
  for (const dim of usedDimensions) {
    itemsByDim.set(
      dim.id,
      dimensionItems
        .filter((i) => i.dimension_id === dim.id)
        .sort((a, b) => a.order - b.order)
    );
  }

  const dimArrays = usedDimensions.map((d) => itemsByDim.get(d.id) ?? []);
  const combos = cartesianProduct(dimArrays);

  return combos.map((combo) => ({
    key: combo.map((i) => i.id).join("|"),
    label: combo.map((i) => i.name).join(" / "),
    dimensionMemberIds: combo.map((i) => i.id),
  }));
}

// ── Convert ColumnDef members to the DimensionMember shape useCellData uses ──

function toDimensionMembers(
  col: ColumnDef,
  dimensions: Dimension[],
  dimensionItems: DimensionItem[]
): DimensionMember[] {
  const itemById = new Map(dimensionItems.map((i) => [i.id, i]));
  return col.dimensionMemberIds.map((memberId) => {
    const item = itemById.get(memberId);
    const dim = dimensions.find((d) => d.id === item?.dimension_id);
    return {
      dimension_id: dim?.id ?? "",
      member_id: memberId,
    };
  });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function DataGrid({
  moduleId,
  lineItems,
  dimensions,
  dimensionItems,
  initialCells,
}: DataGridProps) {
  const { writeCell, getCachedValue, isLoading, error, initCache } = useCellData(moduleId);

  // Hydrate cache with server-side pre-fetched cells (no API writes triggered)
  const hydratedRef = useRef(false);
  useEffect(() => {
    if (hydratedRef.current || !initialCells || initialCells.length === 0) return;
    hydratedRef.current = true;
    // Convert api.ts CellValue (dimension_member_ids: string[]) to
    // useCellData CellValue (dimension_members: DimensionMember[])
    const converted = initialCells.map((cell) => ({
      line_item_id: cell.line_item_id,
      dimension_members: cell.dimension_member_ids.map((memberId) => {
        const item = dimensionItems.find((i) => i.id === memberId);
        return { dimension_id: item?.dimension_id ?? "", member_id: memberId };
      }),
      value: cell.value,
    }));
    initCache(converted);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const columns = useMemo(
    () => buildColumns(lineItems, dimensions, dimensionItems),
    [lineItems, dimensions, dimensionItems]
  );

  // Sort line items
  const sortedLineItems = useMemo(() => {
    if (!sortColumn) return lineItems;
    return [...lineItems].sort((a, b) => {
      const col = columns.find((c) => c.key === sortColumn);
      if (!col) return 0;
      const members = toDimensionMembers(col, dimensions, dimensionItems);
      const aVal = getCachedValue(a.id, members) ?? null;
      const bVal = getCachedValue(b.id, members) ?? null;
      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return 1;
      if (bVal === null) return -1;
      const cmp =
        typeof aVal === "number" && typeof bVal === "number"
          ? aVal - bVal
          : String(aVal).localeCompare(String(bVal));
      return sortDirection === "asc" ? cmp : -cmp;
    });
  }, [lineItems, sortColumn, sortDirection, columns, dimensions, dimensionItems, getCachedValue]);

  const handleSort = useCallback(
    (columnKey: string) => {
      if (sortColumn === columnKey) {
        setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortColumn(columnKey);
        setSortDirection("asc");
      }
    },
    [sortColumn]
  );

  // Row virtualizer
  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: sortedLineItems.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const totalHeight = rowVirtualizer.getTotalSize();
  const virtualItems = rowVirtualizer.getVirtualItems();

  if (lineItems.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white text-sm text-zinc-400">
        No line items in this module.
      </div>
    );
  }

  const topPad = virtualItems.length > 0 ? virtualItems[0].start : 0;
  const lastItem = virtualItems[virtualItems.length - 1];
  const bottomPad =
    lastItem ? totalHeight - (lastItem.start + lastItem.size) : 0;

  return (
    <div className="flex flex-col gap-1">
      {/* Loading / error indicators */}
      {(isLoading || error) && (
        <div className="flex h-5 items-center gap-3 text-xs">
          {isLoading && (
            <span className="flex items-center gap-1 text-blue-500">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-blue-500" />
              Saving...
            </span>
          )}
          {error && (
            <span className="rounded bg-red-50 px-2 py-0.5 text-red-600">
              {error}
            </span>
          )}
        </div>
      )}

      {/* Scrollable grid */}
      <div
        ref={parentRef}
        className="relative overflow-auto rounded-md border border-zinc-200 bg-white shadow-sm"
        style={{ maxHeight: "calc(100vh - 200px)" }}
      >
        <table
          className="border-collapse"
          style={{
            tableLayout: "fixed",
            minWidth: ROW_HEADER_WIDTH + columns.length * COL_WIDTH,
          }}
        >
          <GridHeader
            dimensions={dimensions}
            dimensionItems={dimensionItems}
            columns={columns}
            sortColumn={sortColumn}
            sortDirection={sortDirection}
            onSort={handleSort}
            rowHeaderWidth={ROW_HEADER_WIDTH}
          />

          <tbody>
            {/* Top spacer */}
            {topPad > 0 && <tr style={{ height: topPad }} aria-hidden />}

            {virtualItems.map((virtualRow) => {
              const lineItem = sortedLineItems[virtualRow.index];
              const isEven = virtualRow.index % 2 === 0;

              return (
                <tr
                  key={lineItem.id}
                  style={{ height: ROW_HEIGHT }}
                  className={`group ${isEven ? "bg-white" : "bg-zinc-50"} hover:bg-blue-50/40`}
                >
                  {/* Row header — sticky */}
                  <td
                    style={{ width: ROW_HEADER_WIDTH }}
                    className="sticky left-0 z-10 border-b border-r border-zinc-200 bg-inherit px-3 text-sm font-medium text-zinc-700 group-hover:bg-blue-50/40"
                  >
                    <span className="block truncate" title={lineItem.name}>
                      {lineItem.name}
                    </span>
                    {lineItem.formula && (
                      <span className="block truncate text-[10px] font-mono text-zinc-400">
                        ={lineItem.formula}
                      </span>
                    )}
                  </td>

                  {/* Data cells */}
                  {columns.map((col) => {
                    const members = toDimensionMembers(col, dimensions, dimensionItems);
                    const cachedVal = getCachedValue(lineItem.id, members);
                    const isCalculated = Boolean(lineItem.formula);

                    return (
                      <td
                        key={col.key}
                        style={{ width: COL_WIDTH, minWidth: 90 }}
                        className="h-[36px] border-b border-r border-zinc-200 p-0"
                      >
                        <EditableCell
                          value={cachedVal ?? null}
                          format={lineItem.format as CellFormat}
                          isCalculated={isCalculated}
                          formula={lineItem.formula ?? undefined}
                          onChange={async (newValue) => {
                            await writeCell(lineItem.id, members, newValue);
                          }}
                        />
                      </td>
                    );
                  })}
                </tr>
              );
            })}

            {/* Bottom spacer */}
            {bottomPad > 0 && <tr style={{ height: bottomPad }} aria-hidden />}
          </tbody>
        </table>

        {/* Footer status bar */}
        <div className="sticky bottom-0 left-0 border-t border-zinc-200 bg-zinc-50 px-4 py-1 text-xs text-zinc-400">
          {lineItems.length} line item{lineItems.length !== 1 ? "s" : ""}
          &nbsp;·&nbsp;
          {columns.length} column{columns.length !== 1 ? "s" : ""}
        </div>
      </div>
    </div>
  );
}
