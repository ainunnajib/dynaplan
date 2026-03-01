"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import SubsetMemberEditor from "./SubsetMemberEditor";

interface ListSubsetMember {
  id: string;
  subset_id: string;
  dimension_item_id: string;
}

interface ListSubset {
  id: string;
  dimension_id: string;
  name: string;
  description: string | null;
  is_dynamic: boolean;
  filter_expression: string | null;
  created_at: string;
  updated_at: string;
  members: ListSubsetMember[];
}

interface ListSubsetSummary {
  id: string;
  dimension_id: string;
  name: string;
  description: string | null;
  is_dynamic: boolean;
  filter_expression: string | null;
  created_at: string;
  updated_at: string;
}

interface ResolvedMember {
  id: string;
  name: string;
  code: string;
}

interface DimensionItemOption {
  id: string;
  name: string;
  code: string;
}

interface ListSubsetManagerProps {
  dimensionId: string;
  dimensionItems: DimensionItemOption[];
}

export default function ListSubsetManager({
  dimensionId,
  dimensionItems,
}: ListSubsetManagerProps) {
  const [subsets, setSubsets] = useState<ListSubsetSummary[]>([]);
  const [selectedSubset, setSelectedSubset] = useState<ListSubset | null>(null);
  const [resolvedMembers, setResolvedMembers] = useState<ResolvedMember[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newIsDynamic, setNewIsDynamic] = useState(false);
  const [newFilterExpression, setNewFilterExpression] = useState("");
  const [creating, setCreating] = useState(false);

  const loadSubsets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<ListSubsetSummary[]>(
        `/dimensions/${dimensionId}/subsets`
      );
      setSubsets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subsets");
    } finally {
      setLoading(false);
    }
  }, [dimensionId]);

  useEffect(() => {
    loadSubsets();
  }, [loadSubsets]);

  const selectSubset = useCallback(async (subsetId: string) => {
    setError(null);
    try {
      const [detail, resolved] = await Promise.all([
        fetchApi<ListSubset>(`/subsets/${subsetId}`),
        fetchApi<{ members: ResolvedMember[] }>(`/subsets/${subsetId}/resolved`),
      ]);
      setSelectedSubset(detail);
      setResolvedMembers(resolved.members);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subset");
    }
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: newName.trim(),
        description: newDescription.trim() || null,
        is_dynamic: newIsDynamic,
      };
      if (newIsDynamic && newFilterExpression.trim()) {
        payload.filter_expression = newFilterExpression.trim();
      }
      await fetchApi(`/dimensions/${dimensionId}/subsets`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNewName("");
      setNewDescription("");
      setNewIsDynamic(false);
      setNewFilterExpression("");
      setShowCreateForm(false);
      await loadSubsets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create subset");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (subsetId: string) => {
    if (!confirm("Delete this subset?")) return;
    setError(null);
    try {
      await fetchApi(`/subsets/${subsetId}`, { method: "DELETE" });
      if (selectedSubset?.id === subsetId) {
        setSelectedSubset(null);
        setResolvedMembers([]);
      }
      await loadSubsets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete subset");
    }
  };

  const handleMembersChanged = useCallback(async () => {
    if (selectedSubset) {
      await selectSubset(selectedSubset.id);
    }
  }, [selectedSubset, selectSubset]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">List Subsets</h3>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          {showCreateForm ? "Cancel" : "New Subset"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {showCreateForm && (
        <div className="rounded border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-1.5 text-sm"
              placeholder="Subset name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <input
              type="text"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-1.5 text-sm"
              placeholder="Optional description"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-dynamic"
              checked={newIsDynamic}
              onChange={(e) => setNewIsDynamic(e.target.checked)}
            />
            <label htmlFor="is-dynamic" className="text-sm text-gray-700">
              Dynamic (filter-based)
            </label>
          </div>
          {newIsDynamic && (
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Filter Expression
              </label>
              <input
                type="text"
                value={newFilterExpression}
                onChange={(e) => setNewFilterExpression(e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-1.5 text-sm font-mono"
                placeholder="e.g. name:contains:America"
              />
              <p className="mt-1 text-xs text-gray-500">
                Syntax: field:op:value (field: name/code, op: contains/startswith/eq/matches)
              </p>
            </div>
          )}
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            className="rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-500">Loading subsets...</p>
      ) : subsets.length === 0 ? (
        <p className="text-sm text-gray-500">No subsets defined for this dimension.</p>
      ) : (
        <ul className="divide-y divide-gray-200 rounded border border-gray-200">
          {subsets.map((s) => (
            <li
              key={s.id}
              className={`flex items-center justify-between px-4 py-2 cursor-pointer hover:bg-gray-50 ${
                selectedSubset?.id === s.id ? "bg-blue-50" : ""
              }`}
              onClick={() => selectSubset(s.id)}
            >
              <div>
                <span className="text-sm font-medium">{s.name}</span>
                {s.is_dynamic && (
                  <span className="ml-2 rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700">
                    dynamic
                  </span>
                )}
                {s.description && (
                  <p className="text-xs text-gray-500">{s.description}</p>
                )}
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDelete(s.id);
                }}
                className="text-xs text-red-600 hover:text-red-800"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedSubset && (
        <div className="mt-4 space-y-3 rounded border border-gray-200 p-4">
          <h4 className="text-sm font-semibold">
            {selectedSubset.name}
            {selectedSubset.is_dynamic && " (Dynamic)"}
          </h4>

          {selectedSubset.is_dynamic ? (
            <div>
              <p className="text-xs text-gray-500 mb-2">
                Filter: <code className="bg-gray-100 px-1 rounded">{selectedSubset.filter_expression}</code>
              </p>
              <p className="text-sm font-medium mb-1">
                Resolved Members ({resolvedMembers.length}):
              </p>
              <ul className="space-y-1">
                {resolvedMembers.map((m) => (
                  <li key={m.id} className="text-sm text-gray-700">
                    {m.name} <span className="text-gray-400">({m.code})</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <SubsetMemberEditor
              subsetId={selectedSubset.id}
              subsetType="list"
              currentMembers={selectedSubset.members.map((m) => ({
                memberId: m.id,
                itemId: m.dimension_item_id,
              }))}
              availableItems={dimensionItems.map((di) => ({
                id: di.id,
                label: `${di.name} (${di.code})`,
              }))}
              onMembersChanged={handleMembersChanged}
            />
          )}
        </div>
      )}
    </div>
  );
}
