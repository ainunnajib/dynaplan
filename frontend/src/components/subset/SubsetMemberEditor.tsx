"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";

interface CurrentMember {
  memberId: string;
  itemId: string;
}

interface AvailableItem {
  id: string;
  label: string;
}

interface SubsetMemberEditorProps {
  subsetId: string;
  subsetType: "list" | "lineItem";
  currentMembers: CurrentMember[];
  availableItems: AvailableItem[];
  onMembersChanged: () => void;
}

export default function SubsetMemberEditor({
  subsetId,
  subsetType,
  currentMembers,
  availableItems,
  onMembersChanged,
}: SubsetMemberEditorProps) {
  const [selectedItemIds, setSelectedItemIds] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const memberItemIds = new Set(currentMembers.map((m) => m.itemId));
  const nonMemberItems = availableItems.filter((item) => !memberItemIds.has(item.id));

  const basePath =
    subsetType === "list" ? `/subsets/${subsetId}` : `/line-item-subsets/${subsetId}`;

  const toggleItem = (itemId: string) => {
    setSelectedItemIds((prev) =>
      prev.includes(itemId)
        ? prev.filter((id) => id !== itemId)
        : [...prev, itemId]
    );
  };

  const handleAddMembers = async () => {
    if (selectedItemIds.length === 0) return;
    setAdding(true);
    setError(null);
    try {
      const bodyKey =
        subsetType === "list" ? "dimension_item_ids" : "line_item_ids";
      await fetchApi(`${basePath}/members`, {
        method: "POST",
        body: JSON.stringify({ [bodyKey]: selectedItemIds }),
      });
      setSelectedItemIds([]);
      onMembersChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add members");
    } finally {
      setAdding(false);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    setRemoving(memberId);
    setError(null);
    try {
      await fetchApi(`${basePath}/members/${memberId}`, {
        method: "DELETE",
      });
      onMembersChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove member");
    } finally {
      setRemoving(null);
    }
  };

  const getMemberLabel = (itemId: string): string => {
    const item = availableItems.find((a) => a.id === itemId);
    return item ? item.label : itemId;
  };

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Current members */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-1">
          Current Members ({currentMembers.length})
        </p>
        {currentMembers.length === 0 ? (
          <p className="text-xs text-gray-500">No members yet.</p>
        ) : (
          <ul className="space-y-1">
            {currentMembers.map((m) => (
              <li
                key={m.memberId}
                className="flex items-center justify-between rounded bg-white px-3 py-1.5 text-sm border border-gray-200"
              >
                <span>{getMemberLabel(m.itemId)}</span>
                <button
                  onClick={() => handleRemoveMember(m.memberId)}
                  disabled={removing === m.memberId}
                  className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                >
                  {removing === m.memberId ? "Removing..." : "Remove"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Add members */}
      {nonMemberItems.length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-700 mb-1">
            Add Members
          </p>
          <div className="max-h-48 overflow-y-auto rounded border border-gray-200 bg-white">
            {nonMemberItems.map((item) => (
              <label
                key={item.id}
                className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  checked={selectedItemIds.includes(item.id)}
                  onChange={() => toggleItem(item.id)}
                />
                {item.label}
              </label>
            ))}
          </div>
          <button
            onClick={handleAddMembers}
            disabled={adding || selectedItemIds.length === 0}
            className="mt-2 rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {adding
              ? "Adding..."
              : `Add ${selectedItemIds.length} selected`}
          </button>
        </div>
      )}
    </div>
  );
}
