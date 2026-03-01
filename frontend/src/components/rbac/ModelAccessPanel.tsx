"use client";

import { useCallback, useEffect, useState } from "react";

type ModelPermission = "full_access" | "edit_data" | "view_only" | "no_access";

interface ModelAccessRule {
  user_id: string;
  email: string;
  permission: ModelPermission;
}

interface Props {
  modelId: string;
  token: string;
}

const PERMISSION_COLORS: Record<ModelPermission, string> = {
  full_access: "bg-violet-100 text-violet-800",
  edit_data: "bg-green-100 text-green-800",
  view_only: "bg-blue-100 text-blue-800",
  no_access: "bg-red-100 text-red-800",
};

const PERMISSION_LABELS: Record<ModelPermission, string> = {
  full_access: "Full Access",
  edit_data: "Edit Data",
  view_only: "View Only",
  no_access: "No Access",
};

const PERMISSIONS: ModelPermission[] = ["full_access", "edit_data", "view_only", "no_access"];

export default function ModelAccessPanel({ modelId, token }: Props) {
  const [accessList, setAccessList] = useState<ModelAccessRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [addEmail, setAddEmail] = useState("");
  const [addPermission, setAddPermission] = useState<ModelPermission>("view_only");
  const [addError, setAddError] = useState<string | null>(null);
  const [addLoading, setAddLoading] = useState(false);

  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [removeLoading, setRemoveLoading] = useState(false);

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchAccess = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/models/${modelId}/access`, {
        headers: authHeaders(),
      });
      if (!resp.ok) {
        throw new Error(`Failed to load access rules (${resp.status})`);
      }
      const data: ModelAccessRule[] = await resp.json();
      setAccessList(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [modelId, authHeaders]);

  useEffect(() => {
    fetchAccess();
  }, [fetchAccess]);

  const handleAddAccess = useCallback(async () => {
    if (!addEmail.trim()) return;
    setAddError(null);
    setAddLoading(true);
    try {
      const resp = await fetch(`/api/models/${modelId}/access`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ user_email: addEmail.trim(), permission: addPermission }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setAddEmail("");
      setAddPermission("view_only");
      await fetchAccess();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add access rule");
    } finally {
      setAddLoading(false);
    }
  }, [modelId, addEmail, addPermission, authHeaders, fetchAccess]);

  const handleRemoveAccess = useCallback(
    async (userId: string) => {
      setRemoveLoading(true);
      try {
        const resp = await fetch(`/api/models/${modelId}/access/${userId}`, {
          method: "DELETE",
          headers: authHeaders(),
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || `Error ${resp.status}`);
        }
        setConfirmRemove(null);
        await fetchAccess();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove access rule");
      } finally {
        setRemoveLoading(false);
      }
    },
    [modelId, authHeaders, fetchAccess]
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-900 mb-4">Model Access</h2>

        {/* Add access form */}
        <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4 mb-4">
          <h3 className="text-sm font-medium text-zinc-700 mb-3">Grant Access</h3>
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
              <label className="block text-xs text-zinc-500 mb-1">Permission</label>
              <select
                value={addPermission}
                onChange={(e) => setAddPermission(e.target.value as ModelPermission)}
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
                disabled={addLoading}
              >
                {PERMISSIONS.map((p) => (
                  <option key={p} value={p}>
                    {PERMISSION_LABELS[p]}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={handleAddAccess}
              disabled={!addEmail.trim() || addLoading}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {addLoading ? "Saving..." : "Grant"}
            </button>
          </div>
          {addError && <p className="mt-2 text-xs text-red-600">{addError}</p>}
        </div>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
            {error}
          </div>
        )}

        {/* Access rules table */}
        {loading ? (
          <p className="text-sm text-zinc-400 py-4 text-center">Loading access rules...</p>
        ) : accessList.length === 0 ? (
          <p className="text-sm text-zinc-400 py-4 text-center">No access rules configured.</p>
        ) : (
          <div className="rounded-lg border border-zinc-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 border-b border-zinc-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">User</th>
                  <th className="text-left px-4 py-3 font-medium text-zinc-600">Permission</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {accessList.map((rule) => (
                  <tr key={rule.user_id} className="hover:bg-zinc-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="text-zinc-900">{rule.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${PERMISSION_COLORS[rule.permission]}`}
                      >
                        {PERMISSION_LABELS[rule.permission]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      {confirmRemove === rule.user_id ? (
                        <div className="flex items-center justify-end gap-2">
                          <span className="text-xs text-zinc-500">Remove access?</span>
                          <button
                            type="button"
                            onClick={() => handleRemoveAccess(rule.user_id)}
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
                          onClick={() => setConfirmRemove(rule.user_id)}
                          className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:border-red-300 hover:text-red-600 transition-colors"
                        >
                          Remove
                        </button>
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
