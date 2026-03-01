"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import RollConfirmDialog from "./RollConfirmDialog";

interface ForecastStatusData {
  horizon_months: number;
  periods_elapsed: number;
  periods_remaining: number;
  last_rolled_at: string | null;
  next_roll_suggestion: string | null;
}

interface RollResult {
  periods_rolled: number;
  cells_archived: number;
  new_switchover_period: string | null;
}

interface ForecastStatusProps {
  modelId: string;
  /** Called after a successful roll. */
  onRolled?: (result: RollResult) => void;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ForecastStatus({ modelId, onRolled }: ForecastStatusProps) {
  const [statusData, setStatusData] = useState<ForecastStatusData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRollDialog, setShowRollDialog] = useState(false);

  async function loadStatus() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchApi<ForecastStatusData>(
        `/api/models/${modelId}/forecast/status`
      );
      setStatusData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load forecast status.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, [modelId]);

  function handleRollSuccess(result: RollResult) {
    setShowRollDialog(false);
    loadStatus();
    onRolled?.(result);
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-zinc-500">Loading forecast status...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-red-600">{error}</p>
        <button
          type="button"
          onClick={loadStatus}
          className="mt-3 text-sm text-blue-600 hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!statusData) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-sm text-zinc-500">No forecast configuration found.</p>
      </div>
    );
  }

  const horizonPct =
    statusData.horizon_months > 0
      ? Math.max(
          0,
          Math.min(
            100,
            Math.round(
              (statusData.periods_remaining / statusData.horizon_months) * 100
            )
          )
        )
      : 0;

  return (
    <>
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold text-zinc-900">
              Rolling Forecast Status
            </h2>
            <p className="mt-0.5 text-sm text-zinc-500">
              {statusData.horizon_months}-month horizon
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowRollDialog(true)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            Roll Forward
          </button>
        </div>

        {/* Progress bar */}
        <div className="mt-5">
          <div className="mb-1.5 flex items-center justify-between text-xs text-zinc-500">
            <span>Horizon remaining</span>
            <span>
              {statusData.periods_remaining} of {statusData.horizon_months} months
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-300"
              style={{ width: `${horizonPct}%` }}
            />
          </div>
        </div>

        {/* Stats grid */}
        <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
          <StatCard
            label="Periods Elapsed"
            value={String(statusData.periods_elapsed)}
          />
          <StatCard
            label="Periods Remaining"
            value={String(statusData.periods_remaining)}
          />
          <StatCard
            label="Last Rolled"
            value={formatDateTime(statusData.last_rolled_at)}
          />
          {statusData.next_roll_suggestion && (
            <StatCard
              label="Next Roll Period"
              value={statusData.next_roll_suggestion}
            />
          )}
        </div>
      </div>

      {showRollDialog && (
        <RollConfirmDialog
          modelId={modelId}
          nextPeriod={statusData.next_roll_suggestion}
          onConfirm={handleRollSuccess}
          onCancel={() => setShowRollDialog(false)}
        />
      )}
    </>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-zinc-50 px-3 py-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-zinc-900">{value}</p>
    </div>
  );
}
