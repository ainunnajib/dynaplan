"use client";

import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PipelineStepData {
  id: string;
  pipeline_id: string;
  name: string;
  step_type: string;
  config: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

const STEP_TYPE_LABELS: Record<string, string> = {
  source: "Source",
  transform: "Transform",
  filter: "Filter",
  map: "Map",
  aggregate: "Aggregate",
  publish: "Publish",
};

const STEP_TYPE_COLORS: Record<string, string> = {
  source: "bg-blue-100 text-blue-800",
  transform: "bg-purple-100 text-purple-800",
  filter: "bg-yellow-100 text-yellow-800",
  map: "bg-orange-100 text-orange-800",
  aggregate: "bg-teal-100 text-teal-800",
  publish: "bg-green-100 text-green-800",
};

interface StepConfigProps {
  step: PipelineStepData;
  onDelete: () => void;
  onUpdated: () => void;
}

export function StepConfig({ step, onDelete, onUpdated }: StepConfigProps) {
  const { token } = useAuth();
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(step.name);
  const [editConfig, setEditConfig] = useState(step.config ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {};
      if (editName !== step.name) body.name = editName;
      if (editConfig !== (step.config ?? "")) body.config = editConfig || null;

      const res = await fetch(`${API_BASE}/steps/${step.id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail ?? "Save failed");
        return;
      }
      setEditing(false);
      onUpdated();
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setEditName(step.name);
    setEditConfig(step.config ?? "");
    setEditing(false);
    setError(null);
  };

  const typeLabel = STEP_TYPE_LABELS[step.step_type] ?? step.step_type;
  const typeColor = STEP_TYPE_COLORS[step.step_type] ?? "bg-gray-100 text-gray-800";

  return (
    <div className="border rounded bg-white p-3 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${typeColor}`}>
            {typeLabel}
          </span>
          {editing ? (
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="px-2 py-1 border rounded text-sm"
            />
          ) : (
            <span className="text-sm font-medium">{step.name}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={handleCancel}
                className="px-2 py-1 text-xs border rounded hover:bg-gray-50"
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="px-2 py-1 text-xs border rounded hover:bg-gray-50"
              >
                Edit
              </button>
              <button
                onClick={onDelete}
                className="px-2 py-1 text-xs border border-red-200 text-red-600 rounded hover:bg-red-50"
              >
                Delete
              </button>
            </>
          )}
        </div>
      </div>

      {/* Config area */}
      {editing && (
        <div className="mt-3">
          <label className="text-xs text-gray-500 block mb-1">
            Configuration (JSON)
          </label>
          <textarea
            value={editConfig}
            onChange={(e) => setEditConfig(e.target.value)}
            rows={3}
            placeholder='{"key": "value"}'
            className="w-full px-2 py-1.5 border rounded text-xs font-mono"
          />
        </div>
      )}

      {!editing && step.config && (
        <div className="mt-2">
          <pre className="text-xs text-gray-500 bg-gray-50 p-2 rounded overflow-x-auto">
            {step.config}
          </pre>
        </div>
      )}

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
