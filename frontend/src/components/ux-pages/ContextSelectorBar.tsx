"use client";

import { useCallback } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContextSelectorData {
  id: string;
  page_id: string;
  dimension_id: string;
  label: string;
  allow_multi_select: boolean;
  default_member_id: string | null;
  sort_order: number;
}

export interface MemberOption {
  id: string;
  label: string;
}

export interface SelectorState {
  selector: ContextSelectorData;
  members: MemberOption[];
  selectedIds: string[];
}

interface ContextSelectorBarProps {
  selectors: SelectorState[];
  onChange?: (updated: SelectorState[]) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ContextSelectorBar({
  selectors,
  onChange,
}: ContextSelectorBarProps) {
  const handleSelect = useCallback(
    (selectorIndex: number, memberId: string) => {
      const next = selectors.map((s, i) => {
        if (i !== selectorIndex) return s;

        const isMulti = s.selector.allow_multi_select;
        let newSelected: string[];
        if (memberId === "") {
          newSelected = [];
        } else if (isMulti) {
          if (s.selectedIds.includes(memberId)) {
            newSelected = s.selectedIds.filter((id) => id !== memberId);
          } else {
            newSelected = [...s.selectedIds, memberId];
          }
        } else {
          newSelected = [memberId];
        }

        return { ...s, selectedIds: newSelected };
      });

      onChange?.(next);
    },
    [selectors, onChange]
  );

  if (selectors.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2">
      {selectors.map((s, idx) => (
        <div key={s.selector.id} className="flex items-center gap-2">
          <label className="text-xs font-medium text-zinc-600">
            {s.selector.label}:
          </label>
          {s.selector.allow_multi_select ? (
            <div className="flex flex-wrap gap-1">
              {s.members.map((m) => {
                const isSelected = s.selectedIds.includes(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => handleSelect(idx, m.id)}
                    className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                      isSelected
                        ? "bg-violet-100 text-violet-700 ring-1 ring-violet-300"
                        : "bg-white text-zinc-600 ring-1 ring-zinc-200 hover:bg-zinc-100"
                    }`}
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
          ) : (
            <select
              value={s.selectedIds[0] ?? ""}
              onChange={(e) => handleSelect(idx, e.target.value)}
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs text-zinc-700 focus:outline-none focus:ring-1 focus:ring-violet-400"
            >
              <option value="">-- Select --</option>
              {s.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          )}
        </div>
      ))}
    </div>
  );
}
