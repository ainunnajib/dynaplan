"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// -- Types -------------------------------------------------------------------

interface ALMEnvironment {
  id: string;
  model_id: string;
  env_type: "dev" | "test" | "prod";
  name: string;
  description: string | null;
  source_env_id: string | null;
  is_locked: boolean;
  created_at: string;
  updated_at: string;
}

interface EnvironmentManagerProps {
  modelId: string;
  onSelect?: (env: ALMEnvironment) => void;
}

const ENV_TYPE_LABELS: Record<string, string> = {
  dev: "Development",
  test: "Test",
  prod: "Production",
};

const ENV_TYPE_COLORS: Record<string, string> = {
  dev: "bg-blue-100 text-blue-800",
  test: "bg-yellow-100 text-yellow-800",
  prod: "bg-green-100 text-green-800",
};

// -- Component ---------------------------------------------------------------

export default function EnvironmentManager({
  modelId,
  onSelect,
}: EnvironmentManagerProps) {
  const [environments, setEnvironments] = useState<ALMEnvironment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<"dev" | "test" | "prod">("dev");
  const [newDescription, setNewDescription] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchEnvironments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/models/${modelId}/environments`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!resp.ok) throw new Error("Failed to load environments");
      const data: ALMEnvironment[] = await resp.json();
      setEnvironments(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    fetchEnvironments();
  }, [fetchEnvironments]);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/models/${modelId}/environments`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            env_type: newType,
            name: newName,
            description: newDescription || null,
          }),
        }
      );
      if (!resp.ok) throw new Error("Failed to create environment");
      setShowCreate(false);
      setNewName("");
      setNewDescription("");
      await fetchEnvironments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCreating(false);
    }
  };

  const handleToggleLock = async (env: ALMEnvironment) => {
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/environments/${env.id}/lock`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ is_locked: !env.is_locked }),
        }
      );
      if (!resp.ok) throw new Error("Failed to toggle lock");
      await fetchEnvironments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-sm text-gray-500">
        Loading environments...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Environments</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          {showCreate ? "Cancel" : "New Environment"}
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Name
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="e.g. Development"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Type
            </label>
            <select
              value={newType}
              onChange={(e) =>
                setNewType(e.target.value as "dev" | "test" | "prod")
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="dev">Development</option>
              <option value="test">Test</option>
              <option value="prod">Production</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </div>
      )}

      {/* Environment list */}
      {environments.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          No environments configured yet. Create one to get started.
        </div>
      ) : (
        <div className="space-y-2">
          {environments.map((env) => (
            <div
              key={env.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm cursor-pointer"
              onClick={() => onSelect?.(env)}
            >
              <div className="flex items-center gap-3">
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ENV_TYPE_COLORS[env.env_type]}`}
                >
                  {ENV_TYPE_LABELS[env.env_type]}
                </span>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {env.name}
                  </p>
                  {env.description && (
                    <p className="text-xs text-gray-500">{env.description}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {env.is_locked && (
                  <span className="text-xs text-red-600 font-medium">
                    Locked
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleToggleLock(env);
                  }}
                  className="rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
                >
                  {env.is_locked ? "Unlock" : "Lock"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
