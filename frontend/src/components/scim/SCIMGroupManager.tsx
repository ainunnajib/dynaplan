"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SCIMGroupMember {
  value: string;
  display?: string;
}

interface SCIMGroup {
  id: string;
  displayName: string;
  externalId: string | null;
  members: SCIMGroupMember[];
  meta?: { resourceType: string; location: string };
}

interface SCIMListResponse {
  totalResults: number;
  itemsPerPage: number;
  startIndex: number;
  Resources: SCIMGroup[];
}

interface SCIMGroupManagerProps {
  scimToken: string;
  apiBase?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SCIMGroupManager({
  scimToken,
  apiBase = "http://localhost:8000",
}: SCIMGroupManagerProps) {
  const [groups, setGroups] = useState<SCIMGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${scimToken}`,
  };

  const fetchGroups = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/scim/v2/Groups`, { headers });
      if (!resp.ok) {
        throw new Error(`Failed to load groups: ${resp.statusText}`);
      }
      const data: SCIMListResponse = await resp.json();
      setGroups(data.Resources);
      setTotal(data.totalResults);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [scimToken, apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  async function handleCreateGroup(e: React.FormEvent) {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/scim/v2/Groups`, {
        method: "POST",
        headers,
        body: JSON.stringify({ displayName: newGroupName.trim() }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail ?? `Create failed: ${resp.statusText}`);
      }
      setNewGroupName("");
      await fetchGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteGroup(groupId: string) {
    if (!confirm("Delete this SCIM group?")) return;
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/scim/v2/Groups/${groupId}`, {
        method: "DELETE",
        headers,
      });
      if (!resp.ok && resp.status !== 204) {
        throw new Error(`Delete failed: ${resp.statusText}`);
      }
      await fetchGroups();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-zinc-400 text-sm">
        Loading SCIM groups...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">SCIM Groups</h2>
        <p className="text-sm text-zinc-500 mt-0.5">
          {total} group{total !== 1 ? "s" : ""} provisioned via SCIM.
        </p>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Create group form */}
      <form onSubmit={handleCreateGroup} className="flex gap-2">
        <input
          type="text"
          value={newGroupName}
          onChange={(e) => setNewGroupName(e.target.value)}
          placeholder="New group name"
          className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
        />
        <button
          type="submit"
          disabled={creating || !newGroupName.trim()}
          className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
        >
          {creating ? "Creating..." : "Create Group"}
        </button>
      </form>

      {/* Groups list */}
      {groups.length === 0 ? (
        <div className="text-center py-8 text-zinc-400 text-sm">
          No SCIM groups yet.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {groups.map((group) => (
            <div
              key={group.id}
              className="rounded-lg border border-zinc-200 bg-white"
            >
              <div className="flex items-center justify-between px-4 py-3">
                <button
                  type="button"
                  onClick={() =>
                    setExpandedId(
                      expandedId === group.id ? null : group.id
                    )
                  }
                  className="flex items-center gap-3 text-left flex-1"
                >
                  <span className="text-sm font-medium text-zinc-900">
                    {group.displayName}
                  </span>
                  <span className="text-xs text-zinc-400">
                    {group.members.length} member
                    {group.members.length !== 1 ? "s" : ""}
                  </span>
                  {group.externalId && (
                    <span className="text-xs text-zinc-400 font-mono">
                      ext:{group.externalId}
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteGroup(group.id)}
                  className="text-xs text-red-500 hover:text-red-700 px-2 py-1"
                >
                  Delete
                </button>
              </div>

              {expandedId === group.id && group.members.length > 0 && (
                <div className="border-t border-zinc-100 px-4 py-3">
                  <p className="text-xs font-medium text-zinc-500 mb-2">
                    Members
                  </p>
                  <ul className="flex flex-col gap-1">
                    {group.members.map((m) => (
                      <li
                        key={m.value}
                        className="text-sm text-zinc-700 flex items-center gap-2"
                      >
                        <span className="w-2 h-2 rounded-full bg-violet-400 inline-block" />
                        {m.display || m.value}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
