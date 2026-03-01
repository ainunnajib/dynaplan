"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LogEntry {
  id: string;
  workspace_id: string;
  operation: string;
  resource_type: string;
  resource_id: string;
  external_id: string | null;
  status: "success" | "failed";
  error_message: string | null;
  created_at: string;
}

interface ProvisioningLogProps {
  workspaceId: string;
  token: string;
  apiBase?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OP_LABELS: Record<string, string> = {
  create_user: "Create User",
  update_user: "Update User",
  deactivate_user: "Deactivate User",
  create_group: "Create Group",
  update_group: "Update Group",
  delete_group: "Delete Group",
  add_member: "Add Member",
  remove_member: "Remove Member",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProvisioningLog({
  workspaceId,
  token,
  apiBase = "http://localhost:8000",
}: ProvisioningLogProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${apiBase}/workspaces/${workspaceId}/scim/logs`,
        { headers }
      );
      if (!resp.ok) {
        throw new Error(`Failed to load logs: ${resp.statusText}`);
      }
      const data: LogEntry[] = await resp.json();
      setLogs(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, token, apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-zinc-400 text-sm">
        Loading provisioning logs...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">
            Provisioning Activity
          </h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            Recent SCIM provisioning operations for this workspace.
          </p>
        </div>
        <button
          type="button"
          onClick={fetchLogs}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {logs.length === 0 ? (
        <div className="text-center py-12 text-zinc-400 text-sm">
          No provisioning activity recorded yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-zinc-50 border-b border-zinc-200">
                <th className="text-left px-4 py-2.5 font-medium text-zinc-600">
                  Time
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-zinc-600">
                  Operation
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-zinc-600">
                  Resource
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-zinc-600">
                  Status
                </th>
                <th className="text-left px-4 py-2.5 font-medium text-zinc-600">
                  Details
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50"
                >
                  <td className="px-4 py-2.5 text-zinc-500 whitespace-nowrap">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-800">
                    {OP_LABELS[log.operation] || log.operation}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-zinc-500">{log.resource_type}</span>
                    <span className="text-zinc-300 mx-1">/</span>
                    <span className="font-mono text-xs text-zinc-600">
                      {log.resource_id.slice(0, 8)}...
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        log.status === "success"
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-700"
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-zinc-500 text-xs">
                    {log.external_id && (
                      <span className="font-mono">
                        ext: {log.external_id}
                      </span>
                    )}
                    {log.error_message && (
                      <span className="text-red-600">
                        {log.error_message}
                      </span>
                    )}
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
