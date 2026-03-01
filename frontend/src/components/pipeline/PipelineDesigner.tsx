"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { StepConfig, PipelineStepData } from "./StepConfig";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface PipelineData {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  steps: PipelineStepData[];
}

interface PipelineDesignerProps {
  pipelineId: string;
  onTrigger?: (runId: string) => void;
}

const STEP_TYPE_OPTIONS = [
  { value: "source", label: "Source" },
  { value: "transform", label: "Transform" },
  { value: "filter", label: "Filter" },
  { value: "map", label: "Map" },
  { value: "aggregate", label: "Aggregate" },
  { value: "publish", label: "Publish" },
];

export function PipelineDesigner({ pipelineId, onTrigger }: PipelineDesignerProps) {
  const { token } = useAuth();
  const [pipeline, setPipeline] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; errors: string[] } | null>(null);

  // New step form
  const [newStepName, setNewStepName] = useState("");
  const [newStepType, setNewStepType] = useState("source");
  const [adding, setAdding] = useState(false);

  const fetchPipeline = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/pipelines/${pipelineId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load pipeline");
        return;
      }
      const data = (await res.json()) as PipelineData;
      setPipeline(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, pipelineId]);

  useEffect(() => {
    void fetchPipeline();
  }, [fetchPipeline]);

  const handleAddStep = async () => {
    if (!token || !pipeline || !newStepName.trim()) return;
    setAdding(true);
    try {
      const sortOrder = pipeline.steps.length;
      const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/steps`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: newStepName.trim(),
          step_type: newStepType,
          sort_order: sortOrder,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail ?? "Failed to add step");
        return;
      }
      setNewStepName("");
      setNewStepType("source");
      await fetchPipeline();
    } catch {
      setError("Network error");
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteStep = async (stepId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/steps/${stepId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to delete step");
        return;
      }
      await fetchPipeline();
    } catch {
      setError("Network error");
    }
  };

  const handleStepUpdated = () => {
    void fetchPipeline();
  };

  const handleValidate = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/validate`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Validation request failed");
        return;
      }
      const data = await res.json();
      setValidation(data);
    } catch {
      setError("Network error");
    }
  };

  const handleTrigger = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/pipelines/${pipelineId}/trigger`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail ?? "Failed to trigger pipeline");
        return;
      }
      const run = await res.json();
      onTrigger?.(run.id);
    } catch {
      setError("Network error");
    }
  };

  if (loading) {
    return <div className="p-4 text-gray-500">Loading pipeline...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-600">{error}</div>;
  }

  if (!pipeline) {
    return <div className="p-4 text-gray-500">Pipeline not found</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{pipeline.name}</h2>
          {pipeline.description && (
            <p className="text-sm text-gray-500 mt-1">{pipeline.description}</p>
          )}
          <span
            className={`inline-block mt-1 px-2 py-0.5 text-xs rounded ${
              pipeline.is_active
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {pipeline.is_active ? "Active" : "Inactive"}
          </span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleValidate}
            className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50"
          >
            Validate
          </button>
          <button
            onClick={handleTrigger}
            disabled={!pipeline.is_active}
            className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Trigger Run
          </button>
        </div>
      </div>

      {/* Validation result */}
      {validation && (
        <div
          className={`p-3 rounded text-sm ${
            validation.valid
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}
        >
          {validation.valid ? (
            <span>Pipeline is valid</span>
          ) : (
            <div>
              <span className="font-medium">Validation errors:</span>
              <ul className="list-disc list-inside mt-1">
                {validation.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Steps list */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-700">
          Steps ({pipeline.steps.length})
        </h3>
        {pipeline.steps.length === 0 && (
          <p className="text-sm text-gray-400">No steps yet. Add one below.</p>
        )}
        {pipeline.steps.map((step, index) => (
          <div key={step.id} className="flex items-start gap-3">
            <div className="flex flex-col items-center pt-4">
              <span className="text-xs text-gray-400 font-mono">{index + 1}</span>
              {index < pipeline.steps.length - 1 && (
                <div className="w-px h-8 bg-gray-300 mt-1" />
              )}
            </div>
            <div className="flex-1">
              <StepConfig
                step={step}
                onDelete={() => handleDeleteStep(step.id)}
                onUpdated={handleStepUpdated}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Add step form */}
      <div className="border rounded p-4 bg-gray-50">
        <h4 className="text-sm font-medium mb-3">Add Step</h4>
        <div className="flex gap-2">
          <input
            type="text"
            value={newStepName}
            onChange={(e) => setNewStepName(e.target.value)}
            placeholder="Step name"
            className="flex-1 px-3 py-1.5 border rounded text-sm"
          />
          <select
            value={newStepType}
            onChange={(e) => setNewStepType(e.target.value)}
            className="px-3 py-1.5 border rounded text-sm bg-white"
          >
            {STEP_TYPE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleAddStep}
            disabled={adding || !newStepName.trim()}
            className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {adding ? "Adding..." : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}
