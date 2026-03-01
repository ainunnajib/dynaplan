"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EngineProfile {
  id: string;
  model_id: string;
  profile_type: "classic" | "polaris";
  max_cells: number;
  max_dimensions: number;
  max_line_items: number;
  sparse_optimization: boolean;
  parallel_calc: boolean;
  memory_limit_mb: number;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

interface ProfileRecommendation {
  model_id: string;
  recommended_profile: string;
  reason: string;
  estimated_cells: number;
  dimension_count: number;
  sparsity_ratio: number;
}

interface ProfileSelectorProps {
  modelId: string;
}

export function ProfileSelector({ modelId }: ProfileSelectorProps) {
  const { token } = useAuth();
  const [profile, setProfile] = useState<EngineProfile | null>(null);
  const [recommendation, setRecommendation] =
    useState<ProfileRecommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [profileType, setProfileType] = useState<"classic" | "polaris">(
    "classic"
  );
  const [maxCells, setMaxCells] = useState(10_000_000);
  const [maxDimensions, setMaxDimensions] = useState(20);
  const [maxLineItems, setMaxLineItems] = useState(1000);
  const [sparseOptimization, setSparseOptimization] = useState(false);
  const [parallelCalc, setParallelCalc] = useState(false);
  const [memoryLimitMb, setMemoryLimitMb] = useState(4096);

  const fetchProfile = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = (await res.json()) as EngineProfile;
        setProfile(data);
        setProfileType(data.profile_type);
        setMaxCells(data.max_cells);
        setMaxDimensions(data.max_dimensions);
        setMaxLineItems(data.max_line_items);
        setSparseOptimization(data.sparse_optimization);
        setParallelCalc(data.parallel_calc);
        setMemoryLimitMb(data.memory_limit_mb);
      }
      setError(null);
    } catch {
      setError("Failed to load engine profile");
    } finally {
      setLoading(false);
    }
  }, [token, modelId]);

  const fetchRecommendation = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile/recommend?dimension_count=0&cell_estimate=0&sparsity_ratio=0`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        setRecommendation((await res.json()) as ProfileRecommendation);
      }
    } catch {
      // non-critical
    }
  }, [token, modelId]);

  useEffect(() => {
    void fetchProfile();
    void fetchRecommendation();
  }, [fetchProfile, fetchRecommendation]);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            profile_type: profileType,
            max_cells: maxCells,
            max_dimensions: maxDimensions,
            max_line_items: maxLineItems,
            sparse_optimization: sparseOptimization,
            parallel_calc: parallelCalc,
            memory_limit_mb: memoryLimitMb,
          }),
        }
      );
      if (!res.ok) {
        setError("Failed to save profile");
        return;
      }
      const data = (await res.json()) as EngineProfile;
      setProfile(data);
    } catch {
      setError("Network error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !profile) return;
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        setProfile(null);
        setProfileType("classic");
        setMaxCells(10_000_000);
        setMaxDimensions(20);
        setMaxLineItems(1000);
        setSparseOptimization(false);
        setParallelCalc(false);
        setMemoryLimitMb(4096);
      }
    } catch {
      setError("Failed to delete profile");
    }
  };

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading engine profile...</div>;
  }

  return (
    <div className="space-y-6 rounded-lg border p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Engine Profile</h2>
        {profile && (
          <button
            onClick={handleDelete}
            className="rounded bg-red-100 px-3 py-1 text-sm text-red-700 hover:bg-red-200"
          >
            Remove Profile
          </button>
        )}
      </div>

      {error && (
        <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>
      )}

      {recommendation && !profile && (
        <div className="rounded bg-blue-50 p-3 text-sm text-blue-700">
          <strong>Recommendation:</strong> {recommendation.recommended_profile} --{" "}
          {recommendation.reason}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm font-medium">Profile Type</span>
          <select
            value={profileType}
            onChange={(e) =>
              setProfileType(e.target.value as "classic" | "polaris")
            }
            className="mt-1 block w-full rounded border px-3 py-2"
          >
            <option value="classic">Classic</option>
            <option value="polaris">Polaris</option>
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Max Cells</span>
          <input
            type="number"
            value={maxCells}
            onChange={(e) => setMaxCells(Number(e.target.value))}
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Max Dimensions</span>
          <input
            type="number"
            value={maxDimensions}
            onChange={(e) => setMaxDimensions(Number(e.target.value))}
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Max Line Items</span>
          <input
            type="number"
            value={maxLineItems}
            onChange={(e) => setMaxLineItems(Number(e.target.value))}
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">Memory Limit (MB)</span>
          <input
            type="number"
            value={memoryLimitMb}
            onChange={(e) => setMemoryLimitMb(Number(e.target.value))}
            className="mt-1 block w-full rounded border px-3 py-2"
          />
        </label>
      </div>

      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={sparseOptimization}
            onChange={(e) => setSparseOptimization(e.target.checked)}
          />
          Sparse Optimization
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={parallelCalc}
            onChange={(e) => setParallelCalc(e.target.checked)}
          />
          Parallel Calculation
        </label>
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? "Saving..." : profile ? "Update Profile" : "Set Profile"}
      </button>
    </div>
  );
}
