"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface DiffCell {
  line_item_id: string;
  dimension_key: string;
  original_value: string | null;
  modified_value: string;
}

interface CompareResult {
  scenario_id: string;
  diffs: DiffCell[];
}

interface EvaluatedCell {
  line_item_id: string;
  dimension_key: string;
  value: string | null;
  is_modified: boolean;
}

interface EvalResult {
  scenario_id: string;
  cells: EvaluatedCell[];
}

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface ScenarioCompareProps {
  scenarioId: string;
  scenarioName?: string;
  versions?: Version[];
  onPromoted?: (promotedCells: number) => void;
}

export default function ScenarioCompare({
  scenarioId,
  scenarioName,
  versions = [],
  onPromoted,
}: ScenarioCompareProps) {
  const [compareResult, setCompareResult] = useState<CompareResult | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"diffs" | "all">("diffs");

  // Promote state
  const [targetVersionId, setTargetVersionId] = useState("");
  const [isPromoting, setIsPromoting] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [promoteSuccess, setPromoteSuccess] = useState<string | null>(null);
  const [showPromoteConfirm, setShowPromoteConfirm] = useState(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const [compare, evaluate] = await Promise.all([
          fetchApi<CompareResult>(`/api/scenarios/${scenarioId}/compare`),
          fetchApi<EvalResult>(`/api/scenarios/${scenarioId}/evaluate`),
        ]);
        setCompareResult(compare);
        setEvalResult(evaluate);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load scenario data.");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [scenarioId]);

  async function handlePromote() {
    if (!targetVersionId) {
      setPromoteError("Please select a target version.");
      return;
    }
    setIsPromoting(true);
    setPromoteError(null);
    setPromoteSuccess(null);
    try {
      const result = await fetchApi<{ promoted_cells: number }>(
        `/api/scenarios/${scenarioId}/promote?target_version_id=${targetVersionId}`,
        { method: "POST" }
      );
      setPromoteSuccess(
        `Successfully promoted ${result.promoted_cells} cell${result.promoted_cells !== 1 ? "s" : ""} to the target version.`
      );
      setShowPromoteConfirm(false);
      onPromoted?.(result.promoted_cells);
    } catch (err) {
      setPromoteError(err instanceof Error ? err.message : "Failed to promote scenario.");
    } finally {
      setIsPromoting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <p className="text-sm text-zinc-500">Loading scenario data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      </div>
    );
  }

  const diffs = compareResult?.diffs ?? [];
  const allCells = evalResult?.cells ?? [];
  const modifiedCount = diffs.length;
  const totalCount = allCells.length;

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">
            {scenarioName ? `Compare — ${scenarioName}` : "Scenario Comparison"}
          </h2>
          <p className="mt-0.5 text-sm text-zinc-500">
            {modifiedCount} modified cell{modifiedCount !== 1 ? "s" : ""} out of {totalCount} total
          </p>
        </div>
        {versions.length > 0 && (
          <button
            type="button"
            onClick={() => setShowPromoteConfirm((v) => !v)}
            className="rounded-md bg-green-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
          >
            Promote to Version
          </button>
        )}
      </div>

      {/* Promote panel */}
      {showPromoteConfirm && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-3">
          <p className="text-sm font-medium text-green-800">
            Promote scenario assumptions to a real version. This will overwrite
            existing cell values in the target version.
          </p>
          <div>
            <label className="block text-sm font-medium text-zinc-700">
              Target Version
            </label>
            <select
              value={targetVersionId}
              onChange={(e) => setTargetVersionId(e.target.value)}
              disabled={isPromoting}
              className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            >
              <option value="">-- Select a version --</option>
              {versions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.version_type})
                </option>
              ))}
            </select>
          </div>
          {promoteError && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {promoteError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowPromoteConfirm(false)}
              disabled={isPromoting}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handlePromote}
              disabled={isPromoting || !targetVersionId}
              className="rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {isPromoting ? "Promoting..." : "Confirm Promote"}
            </button>
          </div>
        </div>
      )}

      {promoteSuccess && (
        <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
          {promoteSuccess}
        </p>
      )}

      {/* Tabs */}
      <div className="border-b border-zinc-200">
        <nav className="-mb-px flex gap-4">
          <button
            type="button"
            onClick={() => setActiveTab("diffs")}
            className={`border-b-2 pb-2 text-sm font-medium transition-colors ${
              activeTab === "diffs"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-zinc-500 hover:text-zinc-700"
            }`}
          >
            Differences ({modifiedCount})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`border-b-2 pb-2 text-sm font-medium transition-colors ${
              activeTab === "all"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-zinc-500 hover:text-zinc-700"
            }`}
          >
            All Cells ({totalCount})
          </button>
        </nav>
      </div>

      {/* Diffs tab */}
      {activeTab === "diffs" && (
        <>
          {diffs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-300 py-10 text-center">
              <p className="text-sm text-zinc-500">
                No differences — this scenario has no assumptions yet.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                    <th className="pb-2 pr-4">Line Item</th>
                    <th className="pb-2 pr-4">Dimension Key</th>
                    <th className="pb-2 pr-4">Base Value</th>
                    <th className="pb-2">Scenario Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {diffs.map((diff, idx) => (
                    <tr key={idx} className="hover:bg-amber-50">
                      <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[160px] truncate">
                        {diff.line_item_id}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[180px] truncate">
                        {diff.dimension_key}
                      </td>
                      <td className="py-2.5 pr-4 text-zinc-500 line-through">
                        {diff.original_value ?? (
                          <span className="no-underline text-zinc-300 italic not-italic">—</span>
                        )}
                      </td>
                      <td className="py-2.5 font-semibold text-blue-700">
                        {diff.modified_value}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* All cells tab */}
      {activeTab === "all" && (
        <>
          {allCells.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-300 py-10 text-center">
              <p className="text-sm text-zinc-500">
                No cells found for this scenario.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-200 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                    <th className="pb-2 pr-4">Line Item</th>
                    <th className="pb-2 pr-4">Dimension Key</th>
                    <th className="pb-2 pr-4">Value</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-100">
                  {allCells.map((cell, idx) => (
                    <tr
                      key={idx}
                      className={cell.is_modified ? "bg-amber-50 hover:bg-amber-100" : "hover:bg-zinc-50"}
                    >
                      <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[160px] truncate">
                        {cell.line_item_id}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-xs text-zinc-600 max-w-[180px] truncate">
                        {cell.dimension_key}
                      </td>
                      <td className={`py-2.5 pr-4 ${cell.is_modified ? "font-semibold text-blue-700" : "text-zinc-700"}`}>
                        {cell.value ?? <span className="text-zinc-300 italic">null</span>}
                      </td>
                      <td className="py-2.5">
                        {cell.is_modified ? (
                          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                            Modified
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-500">
                            Base
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
