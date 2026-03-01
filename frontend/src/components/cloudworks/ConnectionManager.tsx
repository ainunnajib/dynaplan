"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ConnectorType = "s3" | "gcs" | "azure_blob" | "sftp" | "http" | "database";

interface Connection {
  id: string;
  model_id: string;
  name: string;
  connector_type: ConnectorType;
  config: Record<string, unknown> | null;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

interface ConnectionManagerProps {
  modelId: string;
}

const CONNECTOR_LABELS: Record<ConnectorType, string> = {
  s3: "Amazon S3",
  gcs: "Google Cloud Storage",
  azure_blob: "Azure Blob Storage",
  sftp: "SFTP",
  http: "HTTP",
  database: "Database",
};

export function ConnectionManager({ modelId }: ConnectionManagerProps) {
  const { token } = useAuth();
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<ConnectorType>("s3");
  const [creating, setCreating] = useState(false);

  const fetchConnections = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/models/${modelId}/connections`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load connections");
        return;
      }
      const data = (await res.json()) as Connection[];
      setConnections(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, modelId]);

  useEffect(() => {
    void fetchConnections();
  }, [fetchConnections]);

  const handleCreate = useCallback(async () => {
    if (!token || !newName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/models/${modelId}/connections`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newName.trim(),
          connector_type: newType,
        }),
      });
      if (res.ok) {
        setNewName("");
        setShowCreate(false);
        void fetchConnections();
      }
    } catch {
      // Silently ignore
    } finally {
      setCreating(false);
    }
  }, [token, modelId, newName, newType, fetchConnections]);

  const handleDelete = useCallback(
    async (connId: string) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/connections/${connId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          void fetchConnections();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchConnections],
  );

  const handleToggleActive = useCallback(
    async (conn: Connection) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/connections/${conn.id}`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ is_active: !conn.is_active }),
        });
        if (res.ok) {
          void fetchConnections();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchConnections],
  );

  if (loading) {
    return <div className="p-4 text-gray-500">Loading connections...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Cloud Connections</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          {showCreate ? "Cancel" : "New Connection"}
        </button>
      </div>

      {showCreate && (
        <div className="rounded border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 block w-full rounded border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
              placeholder="Connection name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Connector Type</label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as ConnectorType)}
              className="mt-1 block w-full rounded border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              {Object.entries(CONNECTOR_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
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

      {connections.length === 0 ? (
        <p className="text-sm text-gray-500">No connections configured yet.</p>
      ) : (
        <div className="divide-y divide-gray-200 rounded border border-gray-200">
          {connections.map((conn) => (
            <div key={conn.id} className="flex items-center justify-between p-3">
              <div>
                <span className="font-medium">{conn.name}</span>
                <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                  {CONNECTOR_LABELS[conn.connector_type]}
                </span>
                <span
                  className={`ml-2 inline-block h-2 w-2 rounded-full ${
                    conn.is_active ? "bg-green-500" : "bg-gray-400"
                  }`}
                  title={conn.is_active ? "Active" : "Inactive"}
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleToggleActive(conn)}
                  className="text-xs text-blue-600 hover:underline"
                >
                  {conn.is_active ? "Deactivate" : "Activate"}
                </button>
                <button
                  onClick={() => handleDelete(conn.id)}
                  className="text-xs text-red-600 hover:underline"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
