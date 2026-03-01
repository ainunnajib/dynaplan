"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface DimensionOption {
  id: string;
  name: string;
}

export interface MemberOption {
  id: string;
  label: string;
}

export interface ContextFilter {
  dimensionId: string;
  label: string;
  members: MemberOption[];
  selectedMemberIds: string[];
}

interface ContextFilterBarProps {
  dashboardId: string;
  /**
   * The dimension filters to display. Each entry describes one dimension
   * with its available members.
   */
  filters: ContextFilter[];
  /**
   * Called when the user changes a filter selection.
   * Receives the full updated filter state.
   */
  onChange?: (updated: ContextFilter[]) => void;
  /**
   * When true, the bar will also persist selections to the backend via
   * POST /dashboards/{id}/context-filters whenever a change is made.
   */
  persistOnChange?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContextFilterBar({
  dashboardId,
  filters: initialFilters,
  onChange,
  persistOnChange = false,
}: ContextFilterBarProps) {
  const [filters, setFilters] = useState<ContextFilter[]>(initialFilters);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Sync prop changes (e.g. parent re-fetches server state)
  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  const handleSelectionChange = useCallback(
    async (dimensionId: string, newSelectedIds: string[]) => {
      const updated = filters.map((f) =>
        f.dimensionId === dimensionId
          ? { ...f, selectedMemberIds: newSelectedIds }
          : f
      );
      setFilters(updated);
      onChange?.(updated);

      if (persistOnChange) {
        setIsSaving(true);
        setSaveError(null);
        try {
          await fetchApi(`/api/dashboards/${dashboardId}/context-filters`, {
            method: "POST",
            body: JSON.stringify({
              filters: updated.map((f) => ({
                dimension_id: f.dimensionId,
                selected_member_ids: f.selectedMemberIds,
                label: f.label,
              })),
            }),
          });
        } catch (err) {
          setSaveError(
            err instanceof Error ? err.message : "Failed to save filters"
          );
        } finally {
          setIsSaving(false);
        }
      }
    },
    [filters, dashboardId, onChange, persistOnChange]
  );

  if (filters.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 bg-white px-4 py-3 shadow-sm">
      {/* Label */}
      <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Filters
      </span>

      {/* One dropdown per dimension */}
      {filters.map((filter) => (
        <FilterDropdown
          key={filter.dimensionId}
          filter={filter}
          onChange={(ids) => handleSelectionChange(filter.dimensionId, ids)}
        />
      ))}

      {/* Saving indicator */}
      {isSaving && (
        <span className="ml-auto text-xs text-zinc-400 animate-pulse">Saving…</span>
      )}
      {saveError && (
        <span className="ml-auto text-xs text-red-500">{saveError}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FilterDropdown — one dimension's filter control
// ---------------------------------------------------------------------------

interface FilterDropdownProps {
  filter: ContextFilter;
  onChange: (selectedIds: string[]) => void;
}

function FilterDropdown({ filter, onChange }: FilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { label, members, selectedMemberIds } = filter;

  const allSelected = selectedMemberIds.length === members.length;
  const noneSelected = selectedMemberIds.length === 0;

  function toggleMember(id: string) {
    const next = selectedMemberIds.includes(id)
      ? selectedMemberIds.filter((s) => s !== id)
      : [...selectedMemberIds, id];
    onChange(next);
  }

  function toggleAll() {
    if (allSelected) {
      onChange([]);
    } else {
      onChange(members.map((m) => m.id));
    }
  }

  // Summary text shown on the button
  let summary: string;
  if (noneSelected) {
    summary = "None";
  } else if (allSelected) {
    summary = "All";
  } else {
    summary = `${selectedMemberIds.length} of ${members.length}`;
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 transition-colors"
      >
        <span className="font-medium">{label}:</span>
        <span className="text-zinc-500">{summary}</span>
        <ChevronIcon
          className={["h-4 w-4 text-zinc-400 transition-transform", isOpen ? "rotate-180" : ""].join(" ")}
        />
      </button>

      {isOpen && (
        <>
          {/* Backdrop to close on outside click */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute left-0 z-20 mt-1 min-w-[160px] rounded-lg border border-zinc-200 bg-white py-1 shadow-lg">
            {/* Select all */}
            <label className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="font-medium">Select all</span>
            </label>
            <div className="my-1 border-t border-zinc-100" />
            {members.map((member) => (
              <label
                key={member.id}
                className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50"
              >
                <input
                  type="checkbox"
                  checked={selectedMemberIds.includes(member.id)}
                  onChange={() => toggleMember(member.id)}
                  className="rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
                />
                {member.label}
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="m19 9-7 7-7-7" />
    </svg>
  );
}
