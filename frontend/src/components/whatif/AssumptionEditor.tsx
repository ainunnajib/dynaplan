"use client";

import { useState, useEffect, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

interface Assumption {
  id: string;
  scenario_id: string;
  line_item_id: string;
  dimension_key: string;
  original_value: string | null;
  modified_value: string;
  note: string | null;
  created_at: string;
}

interface AssumptionEditorProps {
  scenarioId: string;
  scenarioName?: string;
}

export default function AssumptionEditor({
  scenarioId,
  scenarioName,
}: AssumptionEditorProps) {
  const [assumptions, setAssumptions] = useState<Assumption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [newLineItemId, setNewLineItemId] = useState("");
  const [newDimensionKey, setNewDimensionKey] = useState("");
  const [newModifiedValue, setNewModifiedValue] = useState("");
  const [newNote, setNewNote] = useState("");
  const [isAdding, setIsAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  async function loadAssumptions() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<Assumption[]>(
        `/api/scenarios/${scenarioId}/assumptions`
      );
      setAssumptions(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load assumptions."
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadAssumptions();
  }, [scenarioId]);

  async function handleAddAssumption(e: FormEvent) {
    e.preventDefault();
    if (!newLineItemId.trim() || !newDimensionKey.trim() || !newModifiedValue.trim()) {
      setAddError("Line item ID, dimension key, and modified value are required.");
      return;
    }
    setIsAdding(true);
    setAddError(null);
    try {
      const payload: Record<string, unknown> = {
        line_item_id: newLineItemId.trim(),
        dimension_key: newDimensionKey.trim(),
        modified_value: newModifiedValue.trim(),
      };
      if (newNote.trim()) payload.note = newNote.trim();

      const created = await fetchApi<Assumption>(
        `/api/scenarios/${scenarioId}/assumptions`,
        { method: "POST", body: JSON.stringify(payload) }
      );
      setAssumptions((prev) => [...prev, created]);
      setNewLineItemId("");
      setNewDimensionKey("");
      setNewModifiedValue("");
      setNewNote("");
      setShowAddForm(false);
    } catch (err) {
      setAddError(
        err instanceof Error ? err.message : "Failed to add assumption."
      );
    } finally {
      setIsAdding(false);
    }
  }

  async function handleRemoveAssumption(assumptionId: string) {
    if (!confirm("Remove this assumption?")) return;
    try {
      await fetchApi(`/api/assumptions/${assumptionId}`, { method: "DELETE" });
      setAssumptions((prev) => prev.filter((a) => a.id !== assumptionId));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to remove assumption."
      );
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <p className="text-sm text-zinc-500">Loading assumptions...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">
            {scenarioName ? `Assumptions — ${scenarioName}` : "Assumptions"}
          </h2>
          <p className="mt-0.5 text-sm text-zinc-500">
            Override cell values for this scenario.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowAddForm((v) => !v)}
          className="rounded-md bg-blue-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          {showAddForm ? "Cancel" : "+ Add Assumption"}
        </button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <form
          onSubmit={handleAddAssumption}
          className="mb-6 rounded-lg border border-zinc-200 bg-zinc-50 p-4 space-y-3"
        >
          <h3 className="text-sm font-medium text-zinc-800">New Assumption</h3>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-zinc-700">
                Line Item ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newLineItemId}
                onChange={(e) => setNewLineItemId(e.target.value)}
                placeholder="UUID of the line item"
                disabled={isAdding}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700">
                Dimension Key <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newDimensionKey}
                onChange={(e) => setNewDimensionKey(e.target.value)}
                placeholder="e.g. uuid1|uuid2"
                disabled={isAdding}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700">
                Modified Value <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={newModifiedValue}
                onChange={(e) => setNewModifiedValue(e.target.value)}
                placeholder="e.g. 1500000"
                disabled={isAdding}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700">
                Note
              </label>
              <input
                type="text"
                value={newNote}
                onChange={(e) => setNewNote(e.target.value)}
                placeholder="Why this change?"
                disabled={isAdding}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
            </div>
          </div>

          {addError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {addError}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowAddForm(false)}
              disabled={isAdding}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isAdding}
              className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isAdding ? "Adding..." : "Add Assumption"}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Assumptions table */}
      {assumptions.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 py-10 text-center">
          <p className="text-sm text-zinc-500">
            No assumptions yet. Add one to override cell values.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                <th className="pb-2 pr-4">Line Item</th>
                <th className="pb-2 pr-4">Dimension Key</th>
                <th className="pb-2 pr-4">Original</th>
                <th className="pb-2 pr-4">Modified</th>
                <th className="pb-2 pr-4">Note</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {assumptions.map((a) => (
                <tr key={a.id} className="hover:bg-zinc-50">
                  <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[160px] truncate">
                    {a.line_item_id}
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[180px] truncate">
                    {a.dimension_key}
                  </td>
                  <td className="py-2.5 pr-4 text-zinc-500">
                    {a.original_value ?? (
                      <span className="text-zinc-300 italic">none</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 font-semibold text-blue-700">
                    {a.modified_value}
                  </td>
                  <td className="py-2.5 pr-4 text-xs text-zinc-500 max-w-[200px] truncate">
                    {a.note ?? (
                      <span className="text-zinc-300 italic">—</span>
                    )}
                  </td>
                  <td className="py-2.5 text-right">
                    <button
                      type="button"
                      onClick={() => handleRemoveAssumption(a.id)}
                      className="rounded px-2 py-0.5 text-xs text-red-500 hover:bg-red-50 transition-colors"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
