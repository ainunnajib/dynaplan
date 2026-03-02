"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  type ConditionalFormatRule,
  type LineItem,
  type Dimension,
  type DimensionItem,
  type CellValue,
  type SavedViewConfig,
  getLineItemDimensionIds,
  getCellsPage,
  getDimensionItemsPage,
} from "@/lib/api";
import { useCellData, type DimensionMember } from "@/hooks/useCellData";
import { useCollaboration } from "@/hooks/useCollaboration";
import EditableCell from "./EditableCell";
import type { CellFormat } from "./CellFormatting";
import GridHeader, { type ColumnDef } from "./GridHeader";
import { resolveConditionalFormatting } from "./conditionalFormatting";

export interface DataGridProps {
  modelId: string;
  moduleId: string;
  lineItems: LineItem[];
  moduleConditionalFormatRules?: ConditionalFormatRule[];
  dimensions: Dimension[];
  dimensionItems: DimensionItem[];
  /** Initial cells pre-fetched server-side (hydrates the local cache). */
  initialCells?: CellValue[];
  /** Saved-view configuration currently applied from the toolbar. */
  appliedViewConfig?: SavedViewConfig;
  /** Emits the latest grid view configuration when sort state changes. */
  onViewConfigChange?: (viewConfig: SavedViewConfig) => void;
}

const ROW_HEIGHT = 36;
const ROW_HEADER_WIDTH = 220;
const COL_WIDTH = 130;
const MAX_COLUMNS = 250;
const MAX_ITEMS_PER_DIMENSION = 40;
const CELL_PAGE_SIZE = 2000;
const DIMENSION_ITEMS_PAGE_SIZE = 200;

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

function estimateCartesianSize(arrays: unknown[][]): number {
  return arrays.reduce((acc, curr) => acc * Math.max(curr.length, 1), 1);
}

function capDimensionArrays<T>(arrays: T[][], maxColumns: number): T[][] {
  const capped = arrays.map((items) =>
    items.slice(0, Math.max(1, Math.min(items.length, MAX_ITEMS_PER_DIMENSION)))
  );

  let estimated = estimateCartesianSize(capped);
  if (estimated <= maxColumns) return capped;

  // Reduce the widest dimension first until the cartesian product fits.
  while (estimated > maxColumns) {
    let largestIndex = 0;
    for (let i = 1; i < capped.length; i++) {
      if (capped[i].length > capped[largestIndex].length) {
        largestIndex = i;
      }
    }

    const currentLen = capped[largestIndex].length;
    if (currentLen <= 1) break;
    const nextLen = Math.max(1, Math.floor(currentLen / 2));
    capped[largestIndex] = capped[largestIndex].slice(0, nextLen);
    estimated = estimateCartesianSize(capped);
  }

  return capped;
}

// ── Column builder ─────────────────────────────────────────────────────────────

function buildColumns(
  lineItems: LineItem[],
  dimensions: Dimension[],
  dimensionItems: DimensionItem[]
): ColumnDef[] {
  const usedDimIds = new Set<string>();
  for (const li of lineItems) {
    for (const dimId of getLineItemDimensionIds(li)) {
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

  const rawDimArrays = usedDimensions.map((d) => itemsByDim.get(d.id) ?? []);
  const dimArrays = capDimensionArrays(rawDimArrays, MAX_COLUMNS);
  const combos = cartesianProduct(dimArrays);

  return combos.map((combo) => ({
    key: combo.map((i) => i.id).join("|"),
    label: combo.map((i) => i.name).join(" / "),
    dimensionMemberIds: combo.map((i) => i.id),
  }));
}

function collectUsedDimensionIds(lineItems: LineItem[]): string[] {
  const ordered: string[] = [];
  const seen = new Set<string>();
  for (const lineItem of lineItems) {
    for (const dimId of getLineItemDimensionIds(lineItem)) {
      if (seen.has(dimId)) continue;
      seen.add(dimId);
      ordered.push(dimId);
    }
  }
  return ordered;
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
  modelId,
  moduleId,
  lineItems,
  moduleConditionalFormatRules = [],
  dimensions,
  dimensionItems,
  initialCells,
  appliedViewConfig,
  onViewConfigChange,
}: DataGridProps) {
  const {
    writeCell,
    getCachedValue,
    isLoading,
    error,
    initCache,
    invalidateCache,
    applyRemoteCellChange,
  } = useCellData(moduleId);
  const [loadedDimensionItems, setLoadedDimensionItems] = useState<DimensionItem[]>(
    dimensionItems
  );
  const [loadedCellCount, setLoadedCellCount] = useState(0);
  const [totalCellCount, setTotalCellCount] = useState<number | null>(null);

  const usedDimensionIds = useMemo(
    () => collectUsedDimensionIds(lineItems),
    [lineItems]
  );

  useEffect(() => {
    setLoadedDimensionItems(dimensionItems);
  }, [dimensionItems]);

  const loadedDimensionIdsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (dimensionItems.length === 0) return;
    for (const item of dimensionItems) {
      loadedDimensionIdsRef.current.add(item.dimension_id);
    }
  }, [dimensionItems]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      for (const dimensionId of usedDimensionIds) {
        if (loadedDimensionIdsRef.current.has(dimensionId)) continue;
        loadedDimensionIdsRef.current.add(dimensionId);
        try {
          const page = await getDimensionItemsPage(dimensionId, {
            offset: 0,
            limit: DIMENSION_ITEMS_PAGE_SIZE,
          });
          if (cancelled) return;
          setLoadedDimensionItems((prev) => {
            const byId = new Map(prev.map((item) => [item.id, item]));
            for (const item of page.items) {
              byId.set(item.id, item);
            }
            return Array.from(byId.values());
          });
        } catch {
          // Keep rendering with currently loaded members if lazy load fails.
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [usedDimensionIds]);

  const mapMemberIdsToDimensionMembers = useCallback(
    (dimensionMemberIds: string[]): DimensionMember[] => {
      const itemById = new Map(loadedDimensionItems.map((item) => [item.id, item]));
      return dimensionMemberIds.map((memberId) => {
        const item = itemById.get(memberId);
        return {
          dimension_id: item?.dimension_id ?? "",
          member_id: memberId,
        };
      });
    },
    [loadedDimensionItems]
  );

  const hydrateCache = useCallback(
    (cells: CellValue[]) => {
      if (!cells || cells.length === 0) return;
      const converted = cells.map((cell) => ({
        line_item_id: cell.line_item_id,
        dimension_members: mapMemberIdsToDimensionMembers(cell.dimension_member_ids),
        value: cell.value,
      }));
      initCache(converted);
    },
    [initCache, mapMemberIdsToDimensionMembers]
  );

  const paginationOffsetRef = useRef(0);
  const hasMorePagesRef = useRef(true);
  const loadingPageRef = useRef(false);

  const loadNextCellPage = useCallback(async () => {
    if (loadingPageRef.current || !hasMorePagesRef.current) return;

    loadingPageRef.current = true;
    try {
      const page = await getCellsPage(moduleId, {
        offset: paginationOffsetRef.current,
        limit: CELL_PAGE_SIZE,
      });
      hydrateCache(page.cells);
      paginationOffsetRef.current += page.cells.length;
      hasMorePagesRef.current = page.has_more;
      setLoadedCellCount((prev) => prev + page.cells.length);
      setTotalCellCount(page.total_count);
    } catch {
      // Grid remains editable even if a page fetch fails.
    } finally {
      loadingPageRef.current = false;
    }
  }, [hydrateCache, moduleId]);

  useEffect(() => {
    let cancelled = false;

    invalidateCache();
    paginationOffsetRef.current = 0;
    hasMorePagesRef.current = true;
    loadingPageRef.current = false;
    setLoadedCellCount(0);
    setTotalCellCount(null);

    if (initialCells && initialCells.length > 0) {
      hydrateCache(initialCells);
      paginationOffsetRef.current = initialCells.length;
      setLoadedCellCount(initialCells.length);
      return undefined;
    }

    void (async () => {
      if (cancelled) return;
      await loadNextCellPage();
    })();

    return () => {
      cancelled = true;
    };
  }, [hydrateCache, initialCells, invalidateCache, loadNextCellPage]);

  const handleRemoteCellChange = useCallback(
    (payload: Record<string, unknown>) => {
      const lineItemId =
        typeof payload.line_item_id === "string" ? payload.line_item_id : null;
      if (!lineItemId) return;

      const invalidateLineItemIds = Array.isArray(payload.invalidate_line_item_ids)
        ? payload.invalidate_line_item_ids.filter(
            (entry): entry is string => typeof entry === "string"
          )
        : [];
      if (invalidateLineItemIds.length > 0) {
        invalidateCache(invalidateLineItemIds);
      }

      let dimensionMembers: DimensionMember[] = [];
      if (Array.isArray(payload.dimension_members)) {
        dimensionMembers = payload.dimension_members
          .map((member) => {
            if (typeof member !== "object" || member === null) return null;
            const record = member as {
              dimension_id?: unknown;
              member_id?: unknown;
            };
            if (
              typeof record.dimension_id !== "string" ||
              typeof record.member_id !== "string"
            ) {
              return null;
            }
            return {
              dimension_id: record.dimension_id,
              member_id: record.member_id,
            };
          })
          .filter((member): member is DimensionMember => member !== null);
      }

      if (
        dimensionMembers.length === 0 &&
        Array.isArray(payload.dimension_member_ids)
      ) {
        const memberIds = payload.dimension_member_ids.filter(
          (entry): entry is string => typeof entry === "string"
        );
        dimensionMembers = mapMemberIdsToDimensionMembers(memberIds);
      }

      const rawValue = payload.value;
      const value =
        typeof rawValue === "number" ||
        typeof rawValue === "string" ||
        typeof rawValue === "boolean" ||
        rawValue === null
          ? rawValue
          : null;

      applyRemoteCellChange(lineItemId, dimensionMembers, value);
    },
    [applyRemoteCellChange, invalidateCache, mapMemberIdsToDimensionMembers]
  );

  const { isConnected, sendCellChange } = useCollaboration({
    modelId,
    onCellChange: (payload) => {
      handleRemoteCellChange(payload);
    },
  });

  const [sortColumn, setSortColumn] = useState<string | null>(
    appliedViewConfig?.sort.column_key ?? null
  );
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">(
    appliedViewConfig?.sort.direction ?? "asc"
  );

  const columns = useMemo(
    () => buildColumns(lineItems, dimensions, loadedDimensionItems),
    [lineItems, dimensions, loadedDimensionItems]
  );

  useEffect(() => {
    setSortColumn(appliedViewConfig?.sort.column_key ?? null);
    setSortDirection(appliedViewConfig?.sort.direction ?? "asc");
  }, [appliedViewConfig?.sort.column_key, appliedViewConfig?.sort.direction]);

  useEffect(() => {
    if (!onViewConfigChange) return;
    onViewConfigChange({
      row_dims: appliedViewConfig?.row_dims ?? [],
      col_dims: appliedViewConfig?.col_dims ?? usedDimensionIds,
      filters: appliedViewConfig?.filters ?? {},
      sort: {
        column_key: sortColumn,
        direction: sortDirection,
      },
    });
  }, [
    appliedViewConfig?.col_dims,
    appliedViewConfig?.filters,
    appliedViewConfig?.row_dims,
    onViewConfigChange,
    sortColumn,
    sortDirection,
    usedDimensionIds,
  ]);

  // Sort line items
  const sortedLineItems = useMemo(() => {
    if (!sortColumn) return lineItems;
    return [...lineItems].sort((a, b) => {
      const col = columns.find((c) => c.key === sortColumn);
      if (!col) return 0;
      const members = toDimensionMembers(col, dimensions, loadedDimensionItems);
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
  }, [lineItems, sortColumn, sortDirection, columns, dimensions, loadedDimensionItems, getCachedValue]);

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

  useEffect(() => {
    const element = parentRef.current;
    if (!element) return;

    const handleScroll = () => {
      const nearBottom =
        element.scrollTop + element.clientHeight >= element.scrollHeight - 600;
      if (nearBottom) {
        void loadNextCellPage();
      }
    };

    element.addEventListener("scroll", handleScroll);
    handleScroll();

    return () => {
      element.removeEventListener("scroll", handleScroll);
    };
  }, [loadNextCellPage]);

  useEffect(() => {
    const element = parentRef.current;
    if (!element || !hasMorePagesRef.current) return;
    const isViewportUnderfilled =
      element.scrollHeight <= element.clientHeight + 100;
    if (isViewportUnderfilled) {
      void loadNextCellPage();
    }
  }, [columns.length, loadedCellCount, loadNextCellPage, sortedLineItems.length]);

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
        style={{ maxHeight: "calc(100svh - 180px)" }}
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
            dimensionItems={loadedDimensionItems}
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
                    const members = toDimensionMembers(col, dimensions, loadedDimensionItems);
                    const cachedVal = getCachedValue(lineItem.id, members);
                    const isCalculated = Boolean(lineItem.formula);
                    const resolvedFormatting = resolveConditionalFormatting(
                      cachedVal ?? null,
                      [
                        ...moduleConditionalFormatRules,
                        ...(lineItem.conditional_format_rules ?? []),
                      ]
                    );

                    return (
                      <td
                        key={col.key}
                        style={{ width: COL_WIDTH, minWidth: 90 }}
                        className="h-[36px] border-b border-r border-zinc-200 p-0"
                      >
                        <EditableCell
                          value={cachedVal ?? null}
                          format={lineItem.format as CellFormat}
                          displayFormat={resolvedFormatting.displayFormat}
                          leadingIcon={resolvedFormatting.icon}
                          conditionalStyle={{
                            backgroundColor: resolvedFormatting.backgroundColor,
                            textColor: resolvedFormatting.textColor,
                            bold: resolvedFormatting.bold,
                            italic: resolvedFormatting.italic,
                          }}
                          isCalculated={isCalculated}
                          formula={lineItem.formula ?? undefined}
                          onChange={async (newValue) => {
                            await writeCell(lineItem.id, members, newValue);
                            sendCellChange({
                              line_item_id: lineItem.id,
                              dimension_member_ids: members.map((member) => member.member_id),
                              dimension_members: members,
                              value: newValue,
                              invalidate_line_item_ids: [lineItem.id],
                            });
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
          &nbsp;·&nbsp;
          {loadedCellCount}
          {totalCellCount !== null ? `/${totalCellCount}` : ""} cell
          {loadedCellCount !== 1 ? "s" : ""} cached
          &nbsp;·&nbsp;
          realtime {isConnected ? "on" : "offline"}
        </div>
      </div>
    </div>
  );
}
