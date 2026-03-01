"use client";

import {
  type KeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import type { DimensionMember } from "@/lib/pivot-utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface FilterDropdownProps {
  /** Display label for this dropdown (typically the dimension name). */
  label: string;
  /** Flat, ordered list of members (with depth for indentation). */
  members: DimensionMember[];
  /** Currently selected member IDs. */
  selectedIds: string[];
  /** Called with the full new selection whenever it changes. */
  onChange: (selectedIds: string[]) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function matchSearch(member: DimensionMember, query: string): boolean {
  if (!query) return true;
  return member.name.toLowerCase().includes(query.toLowerCase());
}

/**
 * When a member is toggled we also want to include/exclude its descendents
 * for a natural tree-select UX.  We determine descendants by index: all
 * consecutive members after `idx` whose depth > member.depth are children.
 */
function descendantIds(
  members: DimensionMember[],
  idx: number
): string[] {
  const parentDepth = members[idx]!.depth;
  const result: string[] = [];
  for (let i = idx + 1; i < members.length; i++) {
    const m = members[i]!;
    if (m.depth <= parentDepth) break;
    result.push(m.id);
  }
  return result;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function FilterDropdown({
  label,
  members,
  selectedIds,
  onChange,
}: FilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const triggerId = useId();
  const listId = useId();

  const selected = new Set(selectedIds);
  const total = members.length;
  const selectedCount = selectedIds.length;

  // Close on outside click.
  useEffect(() => {
    if (!isOpen) return;
    function handleOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [isOpen]);

  // Focus search on open.
  useEffect(() => {
    if (isOpen) {
      // Defer to allow render.
      setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [isOpen]);

  // Close on Escape.
  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      setIsOpen(false);
    }
  }

  // -------------------------------------------------------------------------
  // Selection helpers
  // -------------------------------------------------------------------------

  function handleSelectAll() {
    onChange(members.map((m) => m.id));
  }

  function handleClear() {
    onChange([]);
  }

  function handleToggle(member: DimensionMember, idx: number) {
    const children = descendantIds(members, idx);
    const allRelated = [member.id, ...children];

    if (selected.has(member.id)) {
      // Deselect this member and all descendants.
      const next = selectedIds.filter((id) => !allRelated.includes(id));
      onChange(next);
    } else {
      // Select this member and all descendants.
      const next = Array.from(new Set([...selectedIds, ...allRelated]));
      onChange(next);
    }
  }

  // -------------------------------------------------------------------------
  // Filtered view
  // -------------------------------------------------------------------------

  const filteredMembers = members.filter((m) => matchSearch(m, search));

  // -------------------------------------------------------------------------
  // Button label
  // -------------------------------------------------------------------------

  let buttonLabel: string;
  if (selectedCount === 0) {
    buttonLabel = "None selected";
  } else if (selectedCount === total) {
    buttonLabel = "All selected";
  } else {
    buttonLabel = `${selectedCount} of ${total} selected`;
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      ref={dropdownRef}
      className="relative w-full"
      onKeyDown={handleKeyDown}
    >
      {/* Trigger button */}
      <button
        id={triggerId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={listId}
        onClick={() => setIsOpen((v) => !v)}
        className={[
          "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2",
          "text-sm transition-colors duration-150",
          "bg-white hover:bg-zinc-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
          isOpen
            ? "border-blue-400 ring-2 ring-blue-200"
            : "border-zinc-300",
        ].join(" ")}
      >
        <span className="flex items-center gap-2 truncate">
          <span className="font-medium text-zinc-800 truncate">{label}</span>
          <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500">
            {buttonLabel}
          </span>
        </span>

        {/* Chevron */}
        <svg
          aria-hidden="true"
          className={[
            "h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-150",
            isOpen ? "rotate-180" : "",
          ].join(" ")}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div
          id={listId}
          role="dialog"
          aria-label={`Filter ${label}`}
          className={[
            "absolute left-0 top-full z-50 mt-1 w-full min-w-[240px]",
            "rounded-xl border border-zinc-200 bg-white shadow-lg",
            "flex flex-col",
          ].join(" ")}
        >
          {/* Search box */}
          <div className="border-b border-zinc-100 px-3 py-2">
            <div className="flex items-center gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-2 py-1">
              <svg
                aria-hidden="true"
                className="h-3.5 w-3.5 shrink-0 text-zinc-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                  clipRule="evenodd"
                />
              </svg>
              <input
                ref={searchRef}
                type="text"
                placeholder="Search…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-transparent text-xs text-zinc-700 placeholder-zinc-400 focus:outline-none"
                aria-label={`Search ${label} members`}
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="text-zinc-400 hover:text-zinc-600"
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
            </div>
          </div>

          {/* Select all / Clear row */}
          <div className="flex items-center justify-between border-b border-zinc-100 px-3 py-1.5">
            <button
              type="button"
              onClick={handleSelectAll}
              className="text-xs font-medium text-blue-600 hover:text-blue-800 focus:outline-none focus-visible:underline"
            >
              Select All
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="text-xs font-medium text-zinc-500 hover:text-zinc-700 focus:outline-none focus-visible:underline"
            >
              Clear
            </button>
          </div>

          {/* Member list */}
          <ul
            role="listbox"
            aria-multiselectable="true"
            aria-label={`${label} members`}
            className="max-h-60 overflow-y-auto py-1"
          >
            {filteredMembers.length === 0 ? (
              <li className="px-3 py-3 text-center text-xs text-zinc-400 italic">
                No members match &ldquo;{search}&rdquo;
              </li>
            ) : (
              filteredMembers.map((member) => {
                const originalIdx = members.indexOf(member);
                const isSelected = selected.has(member.id);
                // Indent 16px per depth level.
                const indent = member.depth * 16;

                return (
                  <li
                    key={member.id}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => handleToggle(member, originalIdx)}
                    className={[
                      "flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm",
                      "transition-colors duration-100 hover:bg-zinc-50",
                      isSelected ? "text-zinc-900" : "text-zinc-600",
                    ].join(" ")}
                    style={{ paddingLeft: `${12 + indent}px` }}
                  >
                    {/* Custom checkbox */}
                    <span
                      aria-hidden="true"
                      className={[
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                        isSelected
                          ? "border-blue-500 bg-blue-500"
                          : "border-zinc-300 bg-white",
                      ].join(" ")}
                    >
                      {isSelected && (
                        <svg
                          viewBox="0 0 12 12"
                          fill="none"
                          className="h-3 w-3"
                        >
                          <path
                            d="M2 6l3 3 5-5"
                            stroke="white"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </span>

                    {/* Member name — hierarchy depth shown via indent */}
                    <span className="truncate">{member.name}</span>
                  </li>
                );
              })
            )}
          </ul>

          {/* Footer count */}
          <div className="border-t border-zinc-100 px-3 py-1.5 text-right">
            <span className="text-xs text-zinc-400">{buttonLabel}</span>
          </div>
        </div>
      )}
    </div>
  );
}
