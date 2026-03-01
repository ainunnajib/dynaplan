"use client";

import { useState, useCallback, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import SpreadDialog from "./SpreadDialog";

interface HierarchyMemberValue {
  member_id: string;
  member_name: string;
  value: number;
  is_parent: boolean;
}

interface HierarchyValuesResponse {
  line_item_id: string;
  parent_member_id: string | null;
  parent_value: number | null;
  children: HierarchyMemberValue[];
}

interface AggregateResponse {
  parent_value: number;
  children_values: Array<{ member_id: string; value: number }>;
}

interface HierarchyViewProps {
  lineItemId: string;
  dimensionId: string;
  /** Parent member UUID; if not provided shows top-level items */
  parentMemberId?: string;
  /** Display name for the parent member */
  parentMemberName?: string;
  /** Called after any cell update so the parent can refresh */
  onDataChanged?: () => void;
}

function formatNumber(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

interface ChildRowProps {
  member: HierarchyMemberValue;
  maxAbsValue: number;
  lineItemId: string;
  onInlineEdit: (memberId: string, value: number) => Promise<void>;
}

function ChildRow({ member, maxAbsValue, lineItemId, onInlineEdit }: ChildRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(String(member.value));
  const [isSaving, setIsSaving] = useState(false);

  const proportion = maxAbsValue > 0 ? Math.abs(member.value) / maxAbsValue : 0;
  const barWidth = `${(proportion * 100).toFixed(1)}%`;

  async function handleBlur() {
    const parsed = parseFloat(editValue);
    if (isNaN(parsed) || parsed === member.value) {
      setEditing(false);
      setEditValue(String(member.value));
      return;
    }
    setIsSaving(true);
    try {
      await onInlineEdit(member.member_id, parsed);
    } finally {
      setIsSaving(false);
      setEditing(false);
    }
  }

  return (
    <div className="flex items-center gap-3 px-4 py-2 hover:bg-zinc-50 transition-colors">
      {/* Member name */}
      <span className="w-36 shrink-0 text-sm text-zinc-700 truncate">
        {member.member_name}
      </span>

      {/* Proportion bar */}
      <div className="flex-1 h-5 bg-zinc-100 rounded overflow-hidden">
        <div
          className="h-full bg-blue-400 rounded transition-all duration-300"
          style={{ width: barWidth }}
          title={`${(proportion * 100).toFixed(1)}%`}
        />
      </div>

      {/* Value (editable) */}
      <div className="w-28 shrink-0 text-right">
        {editing ? (
          <input
            type="number"
            step="any"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") {
                setEditing(false);
                setEditValue(String(member.value));
              }
            }}
            className="w-full rounded border border-blue-400 px-2 py-0.5 text-sm text-right font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
            autoFocus
            disabled={isSaving}
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="w-full text-right text-sm font-mono text-zinc-900 hover:text-blue-600 transition-colors"
            title="Click to edit"
          >
            {formatNumber(member.value)}
          </button>
        )}
      </div>
    </div>
  );
}

export default function HierarchyView({
  lineItemId,
  dimensionId,
  parentMemberId,
  parentMemberName = "Total",
  onDataChanged,
}: HierarchyViewProps) {
  const [data, setData] = useState<HierarchyValuesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAggregating, setIsAggregating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        line_item_id: lineItemId,
        dimension_id: dimensionId,
      });
      if (parentMemberId) {
        params.set("parent_member_id", parentMemberId);
      }
      const result = await fetchApi<HierarchyValuesResponse>(
        `/planning/hierarchy-values?${params.toString()}`
      );
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hierarchy values");
    } finally {
      setIsLoading(false);
    }
  }, [lineItemId, dimensionId, parentMemberId]);

  // Load on first render and whenever key props change
  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleInlineEdit(memberId: string, value: number) {
    await fetchApi("/cells", {
      method: "POST",
      body: JSON.stringify({
        line_item_id: lineItemId,
        dimension_members: [memberId],
        value,
      }),
    });
    await loadData();
    onDataChanged?.();
  }

  async function handleAggregate() {
    if (!parentMemberId) return;
    setIsAggregating(true);
    try {
      await fetchApi<AggregateResponse>("/planning/aggregate", {
        method: "POST",
        body: JSON.stringify({
          line_item_id: lineItemId,
          parent_member_id: parentMemberId,
        }),
      });
      await loadData();
      onDataChanged?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to aggregate");
    } finally {
      setIsAggregating(false);
    }
  }

  function handleSpreadApplied() {
    loadData();
    onDataChanged?.();
  }

  const children = data?.children ?? [];
  const parentValue = data?.parent_value ?? null;
  const maxAbsValue = Math.max(...children.map((c) => Math.abs(c.value)), 1);

  return (
    <div className="rounded-lg border border-zinc-200 bg-white overflow-hidden">
      {/* Header row — parent */}
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-zinc-900">
            {parentMemberName}
          </span>
          {parentValue !== null && (
            <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs font-mono text-zinc-700">
              {formatNumber(parentValue)}
            </span>
          )}
          {parentMemberId && (
            <span className="text-xs text-zinc-400 uppercase tracking-wide">
              Aggregate
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {parentMemberId && children.length > 0 && (
            <>
              <SpreadDialog
                lineItemId={lineItemId}
                parentMemberId={parentMemberId}
                parentMemberName={parentMemberName}
                children={children.map((c) => ({
                  id: c.member_id,
                  name: c.member_name,
                  currentValue: c.value,
                }))}
                onSpread={handleSpreadApplied}
              />
              <button
                type="button"
                onClick={handleAggregate}
                disabled={isAggregating}
                className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
              >
                {isAggregating ? "Aggregating..." : "Aggregate"}
              </button>
            </>
          )}
          <button
            type="button"
            onClick={loadData}
            disabled={isLoading}
            className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            aria-label="Refresh"
          >
            <RefreshIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Loading / error states */}
      {isLoading && (
        <div className="px-4 py-6 text-center text-sm text-zinc-400">
          Loading...
        </div>
      )}
      {error && !isLoading && (
        <div className="px-4 py-3 text-sm text-red-600 bg-red-50">
          {error}
        </div>
      )}

      {/* Children rows */}
      {!isLoading && !error && children.length === 0 && (
        <div className="px-4 py-6 text-center text-sm text-zinc-400">
          No members found.
        </div>
      )}

      {!isLoading && !error && children.length > 0 && (
        <div className="divide-y divide-zinc-100">
          {/* Column headers */}
          <div className="flex items-center gap-3 px-4 py-1.5 bg-zinc-50 border-b border-zinc-100">
            <span className="w-36 shrink-0 text-xs font-medium text-zinc-500">
              Member
            </span>
            <span className="flex-1 text-xs font-medium text-zinc-500">
              Distribution
            </span>
            <span className="w-28 shrink-0 text-right text-xs font-medium text-zinc-500">
              Value
            </span>
          </div>

          {children.map((member) => (
            <ChildRow
              key={member.member_id}
              member={member}
              maxAbsValue={maxAbsValue}
              lineItemId={lineItemId}
              onInlineEdit={handleInlineEdit}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}
