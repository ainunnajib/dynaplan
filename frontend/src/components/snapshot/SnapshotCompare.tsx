"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SnapshotMetadata {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  created_by: string;
  created_at: string;
}

interface EntityDiff {
  added: number;
  removed: number;
  changed: number;
}

interface SnapshotComparison {
  snapshot_id_a: string;
  snapshot_id_b: string;
  snapshot_name_a: string;
  snapshot_name_b: string;
  dimensions: EntityDiff;
  dimension_items: EntityDiff;
  modules: EntityDiff;
  line_items: EntityDiff;
  cell_values: EntityDiff;
  versions: EntityDiff;
  summary: string;
}

interface SnapshotCompareProps {
  modelId: string;
}

const ENTITY_LABELS: Record<string, string> = {
  dimensions: "Dimensions",
  dimension_items: "Dimension Items",
  modules: "Modules",
  line_items: "Line Items",
  cell_values: "Cell Values",
  versions: "Versions",
};

// ── Main component ────────────────────────────────────────────────────────────

export default function SnapshotCompare({ modelId }: SnapshotCompareProps) {
  const [snapshots, setSnapshots] = useState<SnapshotMetadata[]>([]);
  const [selectedA, setSelectedA] = useState<string>("");
  const [selectedB, setSelectedB] = useState<string>("");
  const [comparison, setComparison] = useState<SnapshotComparison | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSnapshots, setIsLoadingSnapshots] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set()
  );

  useEffect(() => {
    async function loadSnapshots() {
      setIsLoadingSnapshots(true);
      try {
        const data = await fetchApi<SnapshotMetadata[]>(
          `/api/models/${modelId}/snapshots`
        );
        setSnapshots(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load snapshots"
        );
      } finally {
        setIsLoadingSnapshots(false);
      }
    }
    loadSnapshots();
  }, [modelId]);

  async function handleCompare() {
    if (!selectedA || !selectedB) return;
    if (selectedA === selectedB) {
      setError("Please select two different snapshots to compare.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setComparison(null);
    try {
      const result = await fetchApi<SnapshotComparison>("/api/snapshots/compare", {
        method: "POST",
        body: JSON.stringify({
          snapshot_a_id: selectedA,
          snapshot_b_id: selectedB,
        }),
      });
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setIsLoading(false);
    }
  }

  function toggleSection(key: string) {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-zinc-900">Compare Snapshots</h2>
        <p className="text-sm text-zinc-500">
          Select two snapshots to see what changed between them.
        </p>
      </div>

      {/* Selector row */}
      {isLoadingSnapshots ? (
        <p className="text-sm text-zinc-400">Loading snapshots...</p>
      ) : snapshots.length < 2 ? (
        <div className="rounded-lg border border-dashed border-zinc-300 py-8 text-center">
          <p className="text-sm text-zinc-500">
            You need at least 2 snapshots to compare.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <SnapshotSelector
            label="Snapshot A (baseline)"
            snapshots={snapshots}
            value={selectedA}
            onChange={setSelectedA}
            excludeId={selectedB}
          />
          <div className="flex items-center justify-center pb-2 text-zinc-400">
            <ArrowRightIcon className="h-5 w-5" />
          </div>
          <SnapshotSelector
            label="Snapshot B (compare to)"
            snapshots={snapshots}
            value={selectedB}
            onChange={setSelectedB}
            excludeId={selectedA}
          />
          <button
            onClick={handleCompare}
            disabled={!selectedA || !selectedB || isLoading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors sm:mb-0"
            type="button"
          >
            {isLoading ? "Comparing..." : "Compare"}
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 font-medium underline"
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Comparison results */}
      {comparison && (
        <ComparisonResults
          comparison={comparison}
          expandedSections={expandedSections}
          onToggleSection={toggleSection}
        />
      )}
    </div>
  );
}

// ── Snapshot selector ─────────────────────────────────────────────────────────

function SnapshotSelector({
  label,
  snapshots,
  value,
  onChange,
  excludeId,
}: {
  label: string;
  snapshots: SnapshotMetadata[];
  value: string;
  onChange: (id: string) => void;
  excludeId: string;
}) {
  return (
    <div className="flex-1">
      <label className="block text-xs font-medium text-zinc-700">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="">Select snapshot...</option>
        {snapshots
          .filter((s) => s.id !== excludeId)
          .map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} — {new Date(s.created_at).toLocaleDateString()}
            </option>
          ))}
      </select>
    </div>
  );
}

// ── Comparison results ────────────────────────────────────────────────────────

function ComparisonResults({
  comparison,
  expandedSections,
  onToggleSection,
}: {
  comparison: SnapshotComparison;
  expandedSections: Set<string>;
  onToggleSection: (key: string) => void;
}) {
  const entityKeys = [
    "dimensions",
    "dimension_items",
    "modules",
    "line_items",
    "cell_values",
    "versions",
  ] as const;

  const hasAnyChanges = entityKeys.some((key) => {
    const diff = comparison[key];
    return diff.added + diff.removed + diff.changed > 0;
  });

  return (
    <div className="space-y-4">
      {/* Summary banner */}
      <div
        className={`rounded-lg border px-4 py-3 ${
          hasAnyChanges
            ? "border-amber-200 bg-amber-50"
            : "border-emerald-200 bg-emerald-50"
        }`}
      >
        <p
          className={`text-sm font-semibold ${
            hasAnyChanges ? "text-amber-800" : "text-emerald-800"
          }`}
        >
          {hasAnyChanges ? "Differences found" : "Snapshots are identical"}
        </p>
        <p
          className={`mt-0.5 text-xs ${
            hasAnyChanges ? "text-amber-700" : "text-emerald-700"
          }`}
        >
          {comparison.summary}
        </p>
      </div>

      {/* Snapshot names */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <p className="text-xs font-medium text-zinc-500">Snapshot A (baseline)</p>
          <p className="mt-0.5 text-sm font-semibold text-zinc-800">
            {comparison.snapshot_name_a}
          </p>
        </div>
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
          <p className="text-xs font-medium text-zinc-500">Snapshot B</p>
          <p className="mt-0.5 text-sm font-semibold text-zinc-800">
            {comparison.snapshot_name_b}
          </p>
        </div>
      </div>

      {/* Per-entity diffs */}
      <div className="space-y-2">
        {entityKeys.map((key) => {
          const diff = comparison[key];
          const totalChanges = diff.added + diff.removed + diff.changed;
          const isExpanded = expandedSections.has(key);

          return (
            <EntityDiffRow
              key={key}
              label={ENTITY_LABELS[key] ?? key}
              diff={diff}
              totalChanges={totalChanges}
              isExpanded={isExpanded}
              onToggle={() => onToggleSection(key)}
            />
          );
        })}
      </div>
    </div>
  );
}

// ── Entity diff row ───────────────────────────────────────────────────────────

function EntityDiffRow({
  label,
  diff,
  totalChanges,
  isExpanded,
  onToggle,
}: {
  label: string;
  diff: EntityDiff;
  totalChanges: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="rounded-md border border-zinc-200 bg-white">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        type="button"
      >
        <span className="text-sm font-medium text-zinc-800">{label}</span>
        <div className="flex items-center gap-3">
          {/* Badge counts */}
          {diff.added > 0 && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              +{diff.added}
            </span>
          )}
          {diff.removed > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
              -{diff.removed}
            </span>
          )}
          {diff.changed > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              ~{diff.changed}
            </span>
          )}
          {totalChanges === 0 && (
            <span className="text-xs text-zinc-400">No changes</span>
          )}
          <ChevronIcon
            className={`h-4 w-4 text-zinc-400 transition-transform ${
              isExpanded ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t border-zinc-100 px-4 py-3">
          {totalChanges === 0 ? (
            <p className="text-xs text-zinc-400">
              No differences in {label.toLowerCase()} between these snapshots.
            </p>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              <DiffStat
                label="Added"
                count={diff.added}
                colorClass="text-emerald-700"
                bgClass="bg-emerald-50"
              />
              <DiffStat
                label="Removed"
                count={diff.removed}
                colorClass="text-red-700"
                bgClass="bg-red-50"
              />
              <DiffStat
                label="Changed"
                count={diff.changed}
                colorClass="text-amber-700"
                bgClass="bg-amber-50"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Diff stat ─────────────────────────────────────────────────────────────────

function DiffStat({
  label,
  count,
  colorClass,
  bgClass,
}: {
  label: string;
  count: number;
  colorClass: string;
  bgClass: string;
}) {
  return (
    <div className={`rounded-md px-3 py-2 ${bgClass}`}>
      <p className={`text-lg font-bold ${colorClass}`}>{count}</p>
      <p className={`text-xs ${colorClass} opacity-80`}>{label}</p>
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
      />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m19 9-7 7-7-7"
      />
    </svg>
  );
}
