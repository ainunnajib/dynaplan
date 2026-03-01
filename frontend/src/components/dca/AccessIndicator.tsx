"use client";

import { useCallback, useEffect, useState } from "react";

interface CellAccess {
  can_read: boolean;
  can_write: boolean;
  reason: string;
}

interface Props {
  lineItemId: string;
  dimensionKey: string;
  token: string;
  /** Optional: compact mode shows only the icon */
  compact?: boolean;
}

export default function AccessIndicator({
  lineItemId,
  dimensionKey,
  token,
  compact = false,
}: Props) {
  const [access, setAccess] = useState<CellAccess | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAccess = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        line_item_id: lineItemId,
        dimension_key: dimensionKey,
      });
      const resp = await fetch(`/api/cells/access-check?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error(`Access check failed (${resp.status})`);
      setAccess(await resp.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [lineItemId, dimensionKey, token]);

  useEffect(() => {
    fetchAccess();
  }, [fetchAccess]);

  if (loading) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-zinc-400" title="Checking access...">
        <span className="inline-block h-2 w-2 rounded-full bg-zinc-300 animate-pulse" />
        {!compact && <span>Checking...</span>}
      </span>
    );
  }

  if (error) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-500" title={error}>
        <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
        {!compact && <span>Error</span>}
      </span>
    );
  }

  if (!access) return null;

  // Determine display state
  let colorClass: string;
  let label: string;
  let icon: string;

  if (!access.can_read) {
    colorClass = "bg-red-400";
    label = "No Access";
    icon = "No Access";
  } else if (!access.can_write) {
    colorClass = "bg-amber-400";
    label = "Read Only";
    icon = "Read Only";
  } else {
    colorClass = "bg-green-400";
    label = "Read/Write";
    icon = "Read/Write";
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs"
      title={`${label}: ${access.reason}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${colorClass}`} />
      {!compact && (
        <span
          className={
            !access.can_read
              ? "text-red-600"
              : !access.can_write
              ? "text-amber-600"
              : "text-green-600"
          }
        >
          {label}
        </span>
      )}
    </span>
  );
}
