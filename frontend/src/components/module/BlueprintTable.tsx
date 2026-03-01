"use client";

import { useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import type { Module, LineItem, Dimension } from "@/lib/api";
import LineItemEditor from "./LineItemEditor";

interface BlueprintTableProps {
  modelId: string;
  modules: Module[];
  moduleLineItems: Record<string, LineItem[]>;
  dimensions: Dimension[];
}

export default function BlueprintTable({
  modelId,
  modules,
  moduleLineItems,
  dimensions,
}: BlueprintTableProps) {
  // Local state so edits are reflected immediately without a full page reload
  const [localLineItems, setLocalLineItems] = useState<Record<string, LineItem[]>>(
    () => ({ ...moduleLineItems })
  );
  const [addingToModule, setAddingToModule] = useState<string | null>(null);
  const [addError, setAddError] = useState<Record<string, string>>({});

  const handleSaved = useCallback((moduleId: string, updated: LineItem) => {
    setLocalLineItems((prev) => ({
      ...prev,
      [moduleId]: (prev[moduleId] ?? []).map((li) =>
        li.id === updated.id ? updated : li
      ),
    }));
  }, []);

  const handleDeleted = useCallback((moduleId: string, lineItemId: string) => {
    setLocalLineItems((prev) => ({
      ...prev,
      [moduleId]: (prev[moduleId] ?? []).filter((li) => li.id !== lineItemId),
    }));
  }, []);

  async function addLineItem(moduleId: string) {
    setAddingToModule(moduleId);
    setAddError((prev) => ({ ...prev, [moduleId]: "" }));
    try {
      const newItem = await fetchApi<LineItem>(
        `/api/modules/${moduleId}/line-items`,
        {
          method: "POST",
          body: JSON.stringify({
            name: "New Line Item",
            format: "number",
            formula: null,
            summary_method: "sum",
            applies_to_dimensions: [],
          }),
        }
      );
      setLocalLineItems((prev) => ({
        ...prev,
        [moduleId]: [...(prev[moduleId] ?? []), newItem],
      }));
    } catch (err) {
      setAddError((prev) => ({
        ...prev,
        [moduleId]: err instanceof Error ? err.message : "Failed to add line item",
      }));
    } finally {
      setAddingToModule(null);
    }
  }

  if (modules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-white py-16 text-center">
        <p className="text-sm text-zinc-500">No modules in this model yet.</p>
        <a
          href={`/models/${modelId}`}
          className="mt-3 text-sm font-medium text-blue-600 hover:underline"
        >
          Go to model overview to create modules
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {modules.map((mod) => {
        const items = localLineItems[mod.id] ?? [];
        return (
          <section
            key={mod.id}
            id={`module-${mod.id}`}
            className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm"
          >
            {/* Module header */}
            <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded bg-violet-100 text-violet-700">
                  <CubeIcon className="h-3.5 w-3.5" />
                </span>
                <span className="text-sm font-semibold text-zinc-800">{mod.name}</span>
                {mod.description && (
                  <span className="text-xs text-zinc-400">— {mod.description}</span>
                )}
                <span className="ml-1 rounded-full bg-zinc-200 px-2 py-0.5 text-xs text-zinc-600">
                  {items.length} {items.length === 1 ? "item" : "items"}
                </span>
              </div>
              <a
                href={`/models/${modelId}/modules/${mod.id}`}
                className="text-xs text-blue-600 hover:underline"
              >
                Open grid
              </a>
            </div>

            {/* Blueprint table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-zinc-100 bg-zinc-50/50">
                    <th className="w-6 px-2 py-2" />
                    <th className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide min-w-[140px]">
                      Line Item Name
                    </th>
                    <th className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide min-w-[110px]">
                      Format
                    </th>
                    <th className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide min-w-[200px]">
                      Formula
                    </th>
                    <th className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide min-w-[110px]">
                      Summary
                    </th>
                    <th className="px-3 py-2 text-xs font-semibold text-zinc-500 uppercase tracking-wide min-w-[180px]">
                      Applies To
                    </th>
                    <th className="w-20 px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-sm text-zinc-400">
                        No line items yet. Click "Add Line Item" below.
                      </td>
                    </tr>
                  ) : (
                    items.map((li) => (
                      <LineItemEditor
                        key={li.id}
                        lineItem={li}
                        dimensions={dimensions}
                        onSaved={(updated) => handleSaved(mod.id, updated)}
                        onDeleted={(id) => handleDeleted(mod.id, id)}
                      />
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Add line item footer */}
            <div className="flex items-center justify-between border-t border-zinc-100 px-4 py-3">
              {addError[mod.id] && (
                <span className="text-xs text-red-500">{addError[mod.id]}</span>
              )}
              <div className="ml-auto">
                <button
                  type="button"
                  onClick={() => void addLineItem(mod.id)}
                  disabled={addingToModule === mod.id}
                  className="flex items-center gap-1.5 rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
                >
                  <PlusIcon className="h-3.5 w-3.5" />
                  {addingToModule === mod.id ? "Adding..." : "Add Line Item"}
                </button>
              </div>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function CubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}
