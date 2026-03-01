"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

type JobStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

interface JobProgressData {
  job_id: string;
  status: JobStatus;
  processed_rows: number;
  total_rows: number | null;
  failed_rows: number;
  percentage: number | null;
}

interface JobProgressProps {
  jobId: string;
  /** Called when the job transitions to completed/failed/cancelled */
  onFinished?: (data: JobProgressData) => void;
  /** Poll interval in ms — defaults to 2000 */
  pollInterval?: number;
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: JobStatus }) {
  const styles: Record<JobStatus, string> = {
    pending: "bg-zinc-100 text-zinc-600",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-600",
    cancelled: "bg-orange-100 text-orange-600",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${styles[status]}`}
    >
      {status}
    </span>
  );
}

// ── Progress bar ───────────────────────────────────────────────────────────────

function ProgressBar({ percentage }: { percentage: number | null }) {
  const pct = percentage ?? 0;
  return (
    <div className="w-full rounded-full bg-zinc-200 h-2 overflow-hidden">
      <div
        className="h-2 rounded-full bg-blue-500 transition-all duration-500"
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

/**
 * JobProgress — polls a bulk job and shows a real-time progress display.
 *
 * Auto-polls every 2 seconds while the job is pending or running.
 * Shows a progress bar, row counts, status badge, and a cancel button.
 */
export default function JobProgress({
  jobId,
  onFinished,
  pollInterval = 2000,
}: JobProgressProps) {
  const [data, setData] = useState<JobProgressData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isActive = (status: JobStatus) =>
    status === "pending" || status === "running";

  async function fetchProgress() {
    const token = getAuthToken();
    try {
      const resp = await fetch(`${API_BASE_URL}/bulk/jobs/${jobId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        setError(`Failed to fetch job status: ${resp.status}`);
        return;
      }
      const jobData: JobProgressData = await resp.json();
      setData(jobData);

      if (!isActive(jobData.status)) {
        // Stop polling
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        onFinished?.(jobData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error fetching job");
    }
  }

  useEffect(() => {
    // Initial fetch
    fetchProgress();

    // Set up polling
    intervalRef.current = setInterval(fetchProgress, pollInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, pollInterval]);

  async function handleCancel() {
    if (!data || !isActive(data.status)) return;
    setCancelling(true);
    const token = getAuthToken();
    try {
      const resp = await fetch(`${API_BASE_URL}/bulk/jobs/${jobId}/cancel`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setError(
          (body as { detail?: string }).detail ?? `Cancel failed: ${resp.status}`
        );
      } else {
        await fetchProgress();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    } finally {
      setCancelling(false);
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <SpinnerIcon className="h-4 w-4 animate-spin" />
        Loading job status…
      </div>
    );
  }

  const pct = data.percentage ?? (data.status === "completed" ? 100 : 0);

  return (
    <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
          Job {jobId.slice(0, 8)}…
        </p>
        <StatusBadge status={data.status} />
      </div>

      {/* Progress bar */}
      <ProgressBar percentage={pct} />

      {/* Row counts */}
      <div className="flex gap-6 text-sm">
        <div>
          <span className="font-semibold text-zinc-800">
            {data.processed_rows.toLocaleString()}
          </span>
          {data.total_rows != null && (
            <span className="text-zinc-400"> / {data.total_rows.toLocaleString()}</span>
          )}
          <p className="text-xs text-zinc-400">Processed</p>
        </div>
        {data.failed_rows > 0 && (
          <div>
            <span className="font-semibold text-red-600">
              {data.failed_rows.toLocaleString()}
            </span>
            <p className="text-xs text-zinc-400">Failed</p>
          </div>
        )}
        {data.percentage != null && (
          <div>
            <span className="font-semibold text-zinc-800">
              {data.percentage.toFixed(1)}%
            </span>
            <p className="text-xs text-zinc-400">Complete</p>
          </div>
        )}
      </div>

      {/* Cancel button */}
      {isActive(data.status) && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
          >
            {cancelling ? "Cancelling…" : "Cancel job"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function SpinnerIcon({ className }: { className?: string }) {
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
        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364-.707.707M6.343 17.657l-.707.707m12.728 0-.707-.707M6.343 6.343l-.707-.707"
      />
    </svg>
  );
}
