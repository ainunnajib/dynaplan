"use client";

import { useState, useRef, useCallback, type HTMLAttributes, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { fetchApi, getLineItemDimensionIds } from "@/lib/api";
import type { LineItem, LineItemFormat, Dimension } from "@/lib/api";
import FormulaInput from "./FormulaInput";
import DimensionSelector from "./DimensionSelector";

type SummaryMethod =
  | "sum"
  | "average"
  | "min"
  | "max"
  | "none"
  | "formula"
  | "first"
  | "last"
  | "opening_balance"
  | "closing_balance"
  | "weighted_average";

interface LineItemEditorProps {
  lineItem: LineItem;
  dimensions: Dimension[];
  onSaved: (updated: LineItem) => void;
  onDeleted: (id: string) => void;
  dragHandleProps?: HTMLAttributes<HTMLSpanElement>;
}

const FORMAT_OPTIONS: { value: LineItemFormat; label: string }[] = [
  { value: "number", label: "Number" },
  { value: "currency", label: "Currency" },
  { value: "percentage", label: "Percentage" },
  { value: "text", label: "Text" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "list", label: "List" },
];

const SUMMARY_OPTIONS: { value: SummaryMethod; label: string }[] = [
  { value: "sum", label: "Sum" },
  { value: "average", label: "Average" },
  { value: "weighted_average", label: "Weighted Average" },
  { value: "min", label: "Min" },
  { value: "max", label: "Max" },
  { value: "first", label: "First" },
  { value: "last", label: "Last" },
  { value: "opening_balance", label: "Opening Balance" },
  { value: "closing_balance", label: "Closing Balance" },
  { value: "none", label: "None" },
  { value: "formula", label: "Formula" },
];

export default function LineItemEditor({
  lineItem,
  dimensions,
  onSaved,
  onDeleted,
  dragHandleProps,
}: LineItemEditorProps) {
  const [name, setName] = useState(lineItem.name);
  const [format, setFormat] = useState<LineItemFormat>(lineItem.format);
  const [formula, setFormula] = useState(lineItem.formula ?? "");
  const [summaryMethod, setSummaryMethod] = useState<SummaryMethod>(
    (lineItem.summary_method as SummaryMethod) ?? "sum"
  );
  const [appliesToIds, setAppliesToIds] = useState<string[]>(
    getLineItemDimensionIds(lineItem)
  );

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isDirty = useRef(false);

  const markDirty = useCallback(() => {
    isDirty.current = true;
  }, []);

  interface SaveOverrides {
    name?: string;
    format?: LineItemFormat;
    formula?: string;
    summaryMethod?: SummaryMethod;
    appliesToIds?: string[];
  }

  async function saveChanges(overrides: SaveOverrides = {}) {
    if (!isDirty.current) return;

    const effectiveName = overrides.name ?? name;
    if (!effectiveName.trim()) {
      setSaveError("Name is required");
      return;
    }

    const effectiveFormat = overrides.format ?? format;
    const effectiveFormula = overrides.formula ?? formula;
    const effectiveSummary = overrides.summaryMethod ?? summaryMethod;
    const effectiveAppliesTo = overrides.appliesToIds ?? appliesToIds;

    setIsSaving(true);
    setSaveError(null);

    try {
      const updated = await fetchApi<LineItem>(
        `/api/line-items/${lineItem.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: effectiveName.trim(),
            format: effectiveFormat,
            formula: effectiveFormula.trim() || null,
            summary_method: effectiveSummary,
            applies_to_dimensions: effectiveAppliesTo,
          }),
        }
      );
      isDirty.current = false;
      onSaved(updated);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await fetchApi(`/api/line-items/${lineItem.id}`, { method: "DELETE" });
      onDeleted(lineItem.id);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Delete failed");
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  }

  function handleKeyDown(e: ReactKeyboardEvent<HTMLTableRowElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void saveChanges();
    }
    if (e.key === "Escape") {
      // Reset to saved values
      setName(lineItem.name);
      setFormat(lineItem.format);
      setFormula(lineItem.formula ?? "");
      setSummaryMethod((lineItem.summary_method as SummaryMethod) ?? "sum");
      setAppliesToIds(getLineItemDimensionIds(lineItem));
      isDirty.current = false;
      setSaveError(null);
    }
  }

  return (
    <tr
      className="group border-b border-zinc-100 hover:bg-zinc-50/50 transition-colors"
      onKeyDown={handleKeyDown}
    >
      {/* Drag handle */}
      <td className="w-6 px-2 text-zinc-300">
        <span
          {...dragHandleProps}
          className="flex cursor-grab items-center active:cursor-grabbing"
          title="Drag to reorder"
        >
          <DragIcon className="h-4 w-4" />
        </span>
      </td>

      {/* Name */}
      <td className="px-3 py-2 min-w-[140px]">
        <input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            markDirty();
          }}
          onBlur={() => void saveChanges()}
          className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-sm text-zinc-900 focus:border-zinc-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
          placeholder="Line item name"
        />
      </td>

      {/* Format */}
      <td className="px-3 py-2 min-w-[110px]">
        <select
          value={format}
          onChange={(e) => {
            const newFormat = e.target.value as LineItemFormat;
            setFormat(newFormat);
            markDirty();
            void saveChanges({ format: newFormat });
          }}
          className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-sm text-zinc-700 focus:border-zinc-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          {FORMAT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </td>

      {/* Formula */}
      <td className="px-3 py-2 min-w-[200px]">
        <FormulaInput
          value={formula}
          onChange={(v) => {
            setFormula(v);
            markDirty();
          }}
          onBlur={() => void saveChanges()}
          placeholder="Optional formula"
          className="w-full"
        />
      </td>

      {/* Summary method */}
      <td className="px-3 py-2 min-w-[110px]">
        <select
          value={summaryMethod}
          onChange={(e) => {
            const newMethod = e.target.value as SummaryMethod;
            setSummaryMethod(newMethod);
            markDirty();
            void saveChanges({ summaryMethod: newMethod });
          }}
          className="w-full rounded border border-transparent bg-transparent px-1.5 py-1 text-sm text-zinc-700 focus:border-zinc-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
        >
          {SUMMARY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </td>

      {/* Applies To */}
      <td className="px-3 py-2 min-w-[180px]">
        <DimensionSelector
          dimensions={dimensions}
          selectedIds={appliesToIds}
          onChange={(ids) => {
            setAppliesToIds(ids);
            markDirty();
            void saveChanges({ appliesToIds: ids });
          }}
        />
      </td>

      {/* Status + Delete */}
      <td className="px-3 py-2 w-20">
        <div className="flex items-center gap-1.5">
          {isSaving && (
            <span className="text-xs text-zinc-400">Saving...</span>
          )}
          {saveError && !showDeleteConfirm && (
            <span className="text-xs text-red-500" title={saveError}>
              Error
            </span>
          )}

          {showDeleteConfirm ? (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="rounded bg-red-600 px-1.5 py-0.5 text-xs text-white hover:bg-red-700 disabled:opacity-50"
              >
                {isDeleting ? "..." : "Yes"}
              </button>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded border border-zinc-300 px-1.5 py-0.5 text-xs text-zinc-600 hover:bg-zinc-50"
              >
                No
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="rounded p-1 text-zinc-300 opacity-100 transition-opacity hover:bg-red-50 hover:text-red-500 md:opacity-0 md:group-hover:opacity-100"
              title="Delete line item"
            >
              <TrashIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function DragIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 24 24">
      <path d="M8.5 6a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM8.5 12a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM8.5 18a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM18.5 6a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM18.5 12a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0ZM18.5 18a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0Z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}
