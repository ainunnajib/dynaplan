"use client";

import { useCallback, useEffect, useState } from "react";

type WorkspaceRole = "owner" | "admin" | "editor" | "viewer";

interface WorkspaceMember {
  user_id: string;
  email: string;
  full_name: string;
  role: WorkspaceRole;
}

interface Props {
  workspaceId: string;
  token: string;
  currentUserId?: string;
}

const ROLE_COLORS: Record<WorkspaceRole, string> = {
  owner: "bg-violet-100 text-violet-800",
  admin: "bg-blue-100 text-blue-800",
  editor: "bg-green-100 text-green-800",
  viewer: "bg-zinc-100 text-zinc-600",
};

const ROLES: WorkspaceRole[] = ["admin", "editor", "viewer"];

export default function MembersPanel({ workspaceId, token, currentUserId }: Props) {
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [addEmail, setAddEmail] = useState("");
  const [addRole, setAddRole] = useState<WorkspaceRole>("viewer");
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [removeLoading, setRemoveLoading] = useState(false);

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchMembers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/workspaces/${workspaceId}/members`, {
        headers: authHeaders(),
      });
      if (!resp.ok) {
        throw new Error(`Failed to load members (${resp.status})`);
      }
      const data: WorkspaceMember[] = await resp.json();
      setMembers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, authHeaders]);

  useEffect(() => {
    fetchMembers();
  }, [fetchMembers]);

  const handleAddMember = useCallback(async () => {
    if (!addEmail.trim()) return;
    setAddError(null);
    setAddLoading(true);
    try {
      const resp = await fetch(`/api/workspaces/${workspaceId}/members`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ user_email: addEmail.trim(), role: addRole }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setAddEmail("");
      setAddRole("viewer");
      await fetchMembers();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add member");
    } finally {
      setAddLoading(false);
    }
  }, [workspaceId, addEmail, addRole, authHeaders, fetchMembers]);

  const handleRoleChange = useCallback(
    async (userId: string, newRole: WorkspaceRole) => {
      try {
        const resp = await fetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
          method: "PATCH",
          headers: authHeaders(),
          body: JSON.stringify({ role: newRole }),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || `Error ${resp.status}`);
        }
        await fetchMembers();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update role");
      }
    },
    [workspaceId, authHeaders, fetchMembers]
  );

  const handleRemoveMember = useCallback(
    async (userId: string) => {
      setRemoveLoading(true);
      try {
        const resp = await fetch(`/api/workspaces/${workspaceId}/members/${userId}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || `Error ${resp.status}`);
        }
        setConfirmRemove(null);
        await fetchMembers();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove member");
      } finally {
        setRemoveLoading(false);
      }
    },
    [workspaceId, authHeaders, fetchMembers]
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 mb-4">Workspace Members</h2>

        {/* Add member form */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 mb-4">
          <h3 className="text-sm font-medium text-zinc-700 mb-3">Add Member</h3>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="block text-xs text-zinc-500 mb-1">Email address</label>
              <input
                type="email"
                value={addEmail}
                onChange={(e) => {
                  setAddEmail(e.target.value);
                  setAddError(null);
                }}
                placeholder="user@example.com"
                className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                disabled={addLoading}
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-500 mb-1">Role</label>
              <select
                value={addRole}
                onChange={(e) => setAddRole(e.target.value as WorkspaceRole)}
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                disabled={addLoading}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r.charAt(0).toUpperCase() + r.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleAddMember}
              disabled={!addEmail.trim() || addLoading}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {addLoading ? "Adding..." : "Add"}
            </button>
          </div>
          {addError && <p className="mt-2 text-xs text-red-600">{addError}</p>}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        {/* Member table */}
        {loading ? (
          <p className="text-sm text-zinc-400 py-4 text-center">Loading members...</p>
        ) : members.length === 0 ? (
          <p className="text-sm text-zinc-400 py-4 text-center">No members yet.</p>
        ) : (
          <div className="rounded-lg border border-zinc-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">User</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">Role</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {members.map((member) => (
                  <tr key={member.user_id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-zinc-900">{member.full_name}</div>
                      <div className="text-xs text-zinc-500">{member.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      {member.role === "owner" ? (
                        <span
                          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_COLORS.owner}`}
                        >
                          Owner
                        </span>
                      ) : (
                        <select
                          value={member.role}
                          onChange={(e) =>
                            handleRoleChange(member.user_id, e.target.value as WorkspaceRole)
                          }
                          className={`rounded-full px-2.5 py-0.5 text-xs font-medium border-0 cursor-pointer focus:ring-2 focus:ring-violet-200 ${ROLE_COLORS[member.role]}`}
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r.charAt(0).toUpperCase() + r.slice(1)}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {member.role !== "owner" && (
                        <>
                          {confirmRemove === member.user_id ? (
                            <div className="flex items-center justify-end gap-2">
                              <span className="text-xs text-zinc-500">Remove member?</span>
                              <button
                                type="button"
                                onClick={() => handleRemoveMember(member.user_id)}
                                disabled={removeLoading}
                                className="rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                              >
                                {removeLoading ? "..." : "Confirm"}
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmRemove(null)}
                                className="rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmRemove(member.user_id)}
                              className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:border-red-300 hover:text-red-600 transition-colors"
                            >
                              Remove
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
