"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import SubsetMemberEditor from "./SubsetMemberEditor";

interface LineItemSubsetMember {
  id: string;
  subset_id: string;
  line_item_id: string;
}

interface LineItemSubset {
  id: string;
  module_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  members: LineItemSubsetMember[];
}

interface LineItemSubsetSummary {
  id: string;
  module_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

interface ResolvedLineItemMember {
  id: string;
  name: string;
}

interface LineItemOption {
  id: string;
  name: string;
}

interface LineItemSubsetManagerProps {
  moduleId: string;
  lineItems: LineItemOption[];
}

export default function LineItemSubsetManager({
  moduleId,
  lineItems,
}: LineItemSubsetManagerProps) {
  const [subsets, setSubsets] = useState<LineItemSubsetSummary[]>([]);
  const [selectedSubset, setSelectedSubset] = useState<LineItemSubset | null>(null);
  const [resolvedMembers, setResolvedMembers] = useState<ResolvedLineItemMember[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const loadSubsets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchApi<LineItemSubsetSummary[]>(
        `/modules/${moduleId}/line-item-subsets`
      );
      setSubsets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subsets");
    } finally {
      setLoading(false);
    }
  }, [moduleId]);

  useEffect(() => {
    loadSubsets();
  }, [loadSubsets]);

  const selectSubset = useCallback(async (subsetId: string) => {
    setError(null);
    try {
      const [detail, resolved] = await Promise.all([
        fetchApi<LineItemSubset>(`/line-item-subsets/${subsetId}`),
        fetchApi<{ members: ResolvedLineItemMember[] }>(
          `/line-item-subsets/${subsetId}/resolved`
        ),
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
      await fetchApi(`/modules/${moduleId}/line-item-subsets`, {
        method: "POST",
        body: JSON.stringify({
          name: newName.trim(),
          description: newDescription.trim() || null,
        }),
      });
      setNewName("");
      setNewDescription("");
      setShowCreateForm(false);
      await loadSubsets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create subset");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (subsetId: string) => {
    if (!confirm("Delete this line item subset?")) return;
    setError(null);
    try {
      await fetchApi(`/line-item-subsets/${subsetId}`, { method: "DELETE" });
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
        <h3 className="text-lg font-semibold">Line Item Subsets</h3>
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
        <p className="text-sm text-gray-500">No line item subsets defined for this module.</p>
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
          <h4 className="text-sm font-semibold">{selectedSubset.name}</h4>
          <SubsetMemberEditor
            subsetId={selectedSubset.id}
            subsetType="lineItem"
            currentMembers={selectedSubset.members.map((m) => ({
              memberId: m.id,
              itemId: m.line_item_id,
            }))}
            availableItems={lineItems.map((li) => ({
              id: li.id,
              label: li.name,
            }))}
            onMembersChanged={handleMembersChanged}
          />
        </div>
      )}
    </div>
  );
}
