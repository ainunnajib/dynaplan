"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// -- Types -------------------------------------------------------------------

interface RevisionTag {
  id: string;
  environment_id: string;
  tag_name: string;
  description: string | null;
  created_by: string;
  snapshot_data: Record<string, unknown> | null;
  created_at: string;
}

interface RevisionTagListProps {
  environmentId: string;
  /** Called when user selects a tag (for promotion or comparison). */
  onSelectTag?: (tag: RevisionTag) => void;
}

// -- Component ---------------------------------------------------------------

export default function RevisionTagList({
  environmentId,
  onSelectTag,
}: RevisionTagListProps) {
  const [tags, setTags] = useState<RevisionTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [tagName, setTagName] = useState("");
  const [tagDescription, setTagDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchTags = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/environments/${environmentId}/tags`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!resp.ok) throw new Error("Failed to load tags");
      const data: RevisionTag[] = await resp.json();
      setTags(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [environmentId]);

  useEffect(() => {
    fetchTags();
  }, [fetchTags]);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/environments/${environmentId}/tags`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            tag_name: tagName,
            description: tagDescription || null,
          }),
        }
      );
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || "Failed to create tag");
      }
      setShowCreate(false);
      setTagName("");
      setTagDescription("");
      await fetchTags();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-6 text-sm text-gray-500">
        Loading revision tags...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-gray-900">
          Revision Tags
        </h3>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {showCreate ? "Cancel" : "New Tag"}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Tag Name
            </label>
            <input
              type="text"
              value={tagName}
              onChange={(e) => setTagName(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="e.g. v1.0.0"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              value={tagDescription}
              onChange={(e) => setTagDescription(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="What changed in this revision?"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !tagName.trim()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create Tag"}
          </button>
        </div>
      )}

      {tags.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No revision tags yet. Create one to snapshot the current state.
        </div>
      ) : (
        <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
          {tags.map((tag) => (
            <li
              key={tag.id}
              className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 cursor-pointer"
              onClick={() => onSelectTag?.(tag)}
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {tag.tag_name}
                </p>
                {tag.description && (
                  <p className="text-xs text-gray-500">{tag.description}</p>
                )}
                <p className="mt-0.5 text-xs text-gray-400">
                  Created{" "}
                  {new Date(tag.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>
              <span className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                {tag.snapshot_data
                  ? `${Object.keys(tag.snapshot_data).length} keys`
                  : "empty"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
