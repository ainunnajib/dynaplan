"use client";

import { useState, useEffect, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

interface Scenario {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  base_version_id: string | null;
  created_by: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  assumption_count: number;
}

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface ScenarioManagerProps {
  modelId: string;
  versions?: Version[];
  onSelectScenario?: (scenario: Scenario) => void;
}

export default function ScenarioManager({
  modelId,
  versions = [],
  onSelectScenario,
}: ScenarioManagerProps) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New scenario form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newBaseVersionId, setNewBaseVersionId] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function loadScenarios() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<Scenario[]>(`/api/models/${modelId}/scenarios`);
      setScenarios(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load scenarios.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadScenarios();
  }, [modelId]);

  async function handleCreateScenario(e: FormEvent) {
    e.preventDefault();
    if (!newName.trim()) {
      setCreateError("Scenario name is required.");
      return;
    }
    setIsCreating(true);
    setCreateError(null);
    try {
      const payload: Record<string, unknown> = {
        name: newName.trim(),
      };
      if (newDescription.trim()) payload.description = newDescription.trim();
      if (newBaseVersionId) payload.base_version_id = newBaseVersionId;

      const created = await fetchApi<Scenario>(`/api/models/${modelId}/scenarios`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setScenarios((prev) => [...prev, created]);
      setNewName("");
      setNewDescription("");
      setNewBaseVersionId("");
      setShowCreateForm(false);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create scenario.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeleteScenario(scenarioId: string) {
    if (!confirm("Delete this scenario? This action cannot be undone.")) return;
    try {
      await fetchApi(`/api/scenarios/${scenarioId}`, { method: "DELETE" });
      setScenarios((prev) => prev.filter((s) => s.id !== scenarioId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete scenario.");
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <p className="text-sm text-zinc-500">Loading scenarios...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">What-if Scenarios</h2>
          <p className="mt-0.5 text-sm text-zinc-500">
            Create and manage temporary scenarios with modified assumptions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreateForm((v) => !v)}
          className="rounded-md bg-blue-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          {showCreateForm ? "Cancel" : "+ New Scenario"}
        </button>
      </div>

      {/* Create form */}
      {showCreateForm && (
        <form
          onSubmit={handleCreateScenario}
          className="mb-6 rounded-lg border border-zinc-200 bg-zinc-50 p-4 space-y-3"
        >
          <h3 className="text-sm font-medium text-zinc-800">New Scenario</h3>

          <div>
            <label className="block text-sm font-medium text-zinc-700">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. Revenue Downside"
              disabled={isCreating}
              className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-700">
              Description
            </label>
            <input
              type="text"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              placeholder="Optional description of this scenario"
              disabled={isCreating}
              className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            />
          </div>

          {versions.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-zinc-700">
                Base Version
              </label>
              <select
                value={newBaseVersionId}
                onChange={(e) => setNewBaseVersionId(e.target.value)}
                disabled={isCreating}
                className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              >
                <option value="">-- None --</option>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.version_type})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-zinc-400">
                The version this scenario branches from.
              </p>
            </div>
          )}

          {createError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {createError}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              disabled={isCreating}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isCreating}
              className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isCreating ? "Creating..." : "Create Scenario"}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      {/* Scenario list */}
      {scenarios.length === 0 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 py-10 text-center">
          <p className="text-sm text-zinc-500">
            No scenarios yet. Create one to start a what-if analysis.
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {scenarios.map((scenario) => (
            <li
              key={scenario.id}
              className="flex items-start justify-between rounded-lg border border-zinc-200 bg-white p-4 hover:border-blue-300 transition-colors"
            >
              <div className="min-w-0 flex-1">
                <button
                  type="button"
                  onClick={() => onSelectScenario?.(scenario)}
                  className="block text-left"
                >
                  <p className="truncate text-sm font-semibold text-zinc-900 hover:text-blue-600">
                    {scenario.name}
                  </p>
                </button>
                {scenario.description && (
                  <p className="mt-0.5 text-xs text-zinc-500">{scenario.description}</p>
                )}
                <div className="mt-1.5 flex gap-3 text-xs text-zinc-400">
                  <span>{scenario.assumption_count} assumption{scenario.assumption_count !== 1 ? "s" : ""}</span>
                  {scenario.base_version_id && (
                    <span>Has base version</span>
                  )}
                  <span>
                    Created {new Date(scenario.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => handleDeleteScenario(scenario.id)}
                className="ml-4 shrink-0 rounded-md px-2 py-1 text-xs text-red-500 hover:bg-red-50 transition-colors"
                title="Delete scenario"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
