"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------

export interface DimensionMember {
  dimension_id: string;
  member_id: string;
}

export interface CellValue {
  line_item_id: string;
  dimension_members: DimensionMember[];
  value: number | string | boolean | null;
}

export interface CellQueryFilter {
  dimension_id: string;
  member_ids: string[];
}

export interface CellQueryResult {
  line_item_id: string;
  dimension_members: DimensionMember[];
  value: number | string | boolean | null;
}

interface ApiCellQueryResult {
  line_item_id: string;
  dimension_members: string[];
  value: number | string | boolean | null;
}

interface PendingWrite {
  lineItemId: string;
  dimensionMembers: DimensionMember[];
  value: number | string | boolean | null;
}

function toApiDimensionMemberIds(
  dimensionMembers: DimensionMember[]
): string[] {
  return dimensionMembers.map((member) => member.member_id);
}

// Key used to store a cell in the local cache map
function cellKey(lineItemId: string, dimensionMembers: DimensionMember[]): string {
  const sortedMembers = [...dimensionMembers].sort((a, b) =>
    a.dimension_id.localeCompare(b.dimension_id)
  );
  const memberPart = sortedMembers
    .map((m) => `${m.dimension_id}:${m.member_id}`)
    .join("|");
  return `${lineItemId}::${memberPart}`;
}

// ------------------------------------------------------------------
// Hook
// ------------------------------------------------------------------

export function useCellData(_moduleId: string) {
  void _moduleId;
  const { token } = useAuth();

  // Local cache: cellKey → value
  const [cellCache, setCellCache] = useState<Map<string, number | string | boolean | null>>(
    new Map()
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pending debounced writes queue
  const pendingWritesRef = useRef<Map<string, PendingWrite>>(new Map());
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const authHeaders = useCallback(
    (): Record<string, string> => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token]
  );

  // ---- queryCells -------------------------------------------------------
  const queryCells = useCallback(
    async (
      lineItemId: string,
      filters: CellQueryFilter[]
    ): Promise<CellQueryResult[]> => {
      setIsLoading(true);
      setError(null);
      try {
        const dimensionFilters = filters.reduce<Record<string, string[]>>(
          (acc, filter) => {
            acc[filter.dimension_id] = filter.member_ids;
            return acc;
          },
          {}
        );
        const res = await fetch(`${API_BASE}/cells/query`, {
          method: "POST",
          headers: authHeaders(),
          body: JSON.stringify({
            line_item_id: lineItemId,
            dimension_filters: Object.keys(dimensionFilters).length
              ? dimensionFilters
              : undefined,
          }),
        });
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
            detail?: string;
          };
          throw new Error(body.error ?? body.detail ?? "Query failed");
        }
        const apiResults = (await res.json()) as ApiCellQueryResult[];
        const results: CellQueryResult[] = apiResults.map((result) => ({
          line_item_id: result.line_item_id,
          dimension_members: result.dimension_members.map((memberId) => ({
            dimension_id: "",
            member_id: memberId,
          })),
          value: result.value,
        }));
        // Populate cache
        setCellCache((prev) => {
          const next = new Map(prev);
          for (const r of results) {
            next.set(cellKey(r.line_item_id, r.dimension_members), r.value);
          }
          return next;
        });
        return results;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Query failed";
        setError(msg);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [authHeaders]
  );

  // ---- flush pending debounced writes -----------------------------------
  const flushPendingWrites = useCallback(async () => {
    const pending = pendingWritesRef.current;
    if (pending.size === 0) return;

    const cells = Array.from(pending.values()).map((p) => ({
      line_item_id: p.lineItemId,
      dimension_members: toApiDimensionMemberIds(p.dimensionMembers),
      value: p.value,
    }));
    // Clear before the request so new edits can accumulate
    pendingWritesRef.current = new Map();

    // Save pre-write snapshot for potential rollback
    let snapshot: Map<string, number | string | boolean | null> | null = null;
    setCellCache((prev) => {
      snapshot = new Map(prev);
      return prev;
    });

    try {
      const res = await fetch(`${API_BASE}/cells/bulk`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ cells }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as {
          error?: string;
          detail?: string;
        };
        throw new Error(body.error ?? body.detail ?? "Bulk save failed");
      }
    } catch (err) {
      // Revert optimistic updates
      if (snapshot) {
        setCellCache(snapshot);
      }
      const msg = err instanceof Error ? err.message : "Bulk save failed";
      setError(msg);
    }
  }, [authHeaders]);

  // Schedule a debounced flush (300 ms window)
  const scheduledFlush = useCallback(() => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null;
      void flushPendingWrites();
    }, 300);
  }, [flushPendingWrites]);

  // ---- writeCell --------------------------------------------------------
  const writeCell = useCallback(
    async (
      lineItemId: string,
      dimensionMembers: DimensionMember[],
      value: number | string | boolean | null
    ): Promise<void> => {
      const key = cellKey(lineItemId, dimensionMembers);

      // Optimistic update
      setCellCache((prev) => {
        const next = new Map(prev);
        next.set(key, value);
        return next;
      });

      // Queue for debounced bulk save
      pendingWritesRef.current.set(key, { lineItemId, dimensionMembers, value });
      scheduledFlush();
    },
    [scheduledFlush]
  );

  // ---- writeCellsBulk ---------------------------------------------------
  const writeCellsBulk = useCallback(
    async (cells: CellValue[]): Promise<void> => {
      // Optimistic update
      setCellCache((prev) => {
        const next = new Map(prev);
        for (const c of cells) {
          next.set(cellKey(c.line_item_id, c.dimension_members), c.value);
        }
        return next;
      });

      // Snapshot for rollback
      let snapshot: Map<string, number | string | boolean | null> | null = null;
      setCellCache((prev) => {
        snapshot = new Map(prev);
        return prev;
      });

      try {
      const res = await fetch(`${API_BASE}/cells/bulk`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          cells: cells.map((cell) => ({
            line_item_id: cell.line_item_id,
            dimension_members: toApiDimensionMemberIds(cell.dimension_members),
            value: cell.value,
          })),
        }),
      });
        if (!res.ok) {
          const body = (await res.json().catch(() => ({}))) as {
            error?: string;
            detail?: string;
          };
          throw new Error(body.error ?? body.detail ?? "Bulk write failed");
        }
      } catch (err) {
        if (snapshot) {
          setCellCache(snapshot);
        }
        const msg = err instanceof Error ? err.message : "Bulk write failed";
        setError(msg);
        throw err;
      }
    },
    [authHeaders]
  );

  // Flush any remaining pending writes when the component unmounts
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current !== null) {
        clearTimeout(debounceTimerRef.current);
      }
      void flushPendingWrites();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Helper: read a cached cell value
  const getCachedValue = useCallback(
    (
      lineItemId: string,
      dimensionMembers: DimensionMember[]
    ): number | string | boolean | null | undefined => {
      return cellCache.get(cellKey(lineItemId, dimensionMembers));
    },
    [cellCache]
  );

  // ---- initCache --------------------------------------------------------
  /**
   * Pre-populate the cache with server-fetched values without triggering
   * any API writes. Useful for hydrating from SSR data.
   */
  const initCache = useCallback(
    (cells: CellValue[]) => {
      setCellCache((prev) => {
        const next = new Map(prev);
        for (const c of cells) {
          next.set(cellKey(c.line_item_id, c.dimension_members), c.value);
        }
        return next;
      });
    },
    []
  );

  return {
    cellCache,
    isLoading,
    error,
    writeCell,
    writeCellsBulk,
    queryCells,
    getCachedValue,
    initCache,
  };
}
