"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface StepLogData {
  id: string;
  run_id: string;
  step_id: string;
  status: string;
  records_in: number | null;
  records_out: number | null;
  started_at: string | null;
  completed_at: string | null;
  log_output: string | null;
}

interface RunDetailData {
  id: string;
  pipeline_id: string;
  status: string;
  triggered_by: string;
  total_steps: number;
  completed_steps: number;
  error_step_id: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  step_logs: StepLogData[];
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-yellow-100 text-yellow-800",
  skipped: "bg-gray-100 text-gray-500",
};

interface RunMonitorProps {
  runId: string;
  /** Poll interval in ms; 0 to disable auto-refresh. Default: 3000 */
  pollInterval?: number;
}

export function RunMonitor({ runId, pollInterval = 3000 }: RunMonitorProps) {
  const { token } = useAuth();
  const [run, setRun] = useState<RunDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isTerminal = run
    ? ["completed", "failed", "cancelled"].includes(run.status)
    : false;

  const fetchRun = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/pipeline-runs/${runId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load run");
        return;
      }
      const data = (await res.json()) as RunDetailData;
      setRun(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, runId]);

  useEffect(() => {
    void fetchRun();
  }, [fetchRun]);

  // Auto-poll while run is active
  useEffect(() => {
    if (isTerminal || pollInterval <= 0) return;
    const timer = setInterval(() => {
      void fetchRun();
    }, pollInterval);
    return () => clearInterval(timer);
  }, [isTerminal, pollInterval, fetchRun]);

  const handleCancel = async () => {
    if (!token || !run) return;
    try {
      const res = await fetch(`${API_BASE}/pipeline-runs/${runId}/cancel`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail ?? "Failed to cancel run");
        return;
      }
      await fetchRun();
    } catch {
      setError("Network error");
    }
  };

  if (loading) {
    return <div className="p-4 text-gray-500">Loading run...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-600">{error}</div>;
  }

  if (!run) {
    return <div className="p-4 text-gray-500">Run not found</div>;
  }

  const statusColor = STATUS_COLORS[run.status] ?? "bg-gray-100 text-gray-800";
  const progressPct =
    run.total_steps > 0
      ? Math.round((run.completed_steps / run.total_steps) * 100)
      : 0;

  return (
    <div className="space-y-4">
      {/* Run header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${statusColor}`}>
            {run.status}
          </span>
          <span className="text-sm text-gray-500">
            {run.completed_steps}/{run.total_steps} steps
          </span>
        </div>
        {!isTerminal && (
          <button
            onClick={handleCancel}
            className="px-3 py-1.5 text-sm border border-red-200 text-red-600 rounded hover:bg-red-50"
          >
            Cancel Run
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${
            run.status === "failed" ? "bg-red-500" : "bg-blue-500"
          }`}
          style={{ width: `${progressPct}%` }}
        />
      </div>

      {/* Error message */}
      {run.error_message && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
          <span className="font-medium">Error: </span>
          {run.error_message}
        </div>
      )}

      {/* Timestamps */}
      <div className="flex gap-4 text-xs text-gray-500">
        <span>Created: {new Date(run.created_at).toLocaleString()}</span>
        {run.started_at && (
          <span>Started: {new Date(run.started_at).toLocaleString()}</span>
        )}
        {run.completed_at && (
          <span>Completed: {new Date(run.completed_at).toLocaleString()}</span>
        )}
      </div>

      {/* Step logs */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-gray-700">Step Logs</h3>
        {run.step_logs.length === 0 && (
          <p className="text-sm text-gray-400">No step logs</p>
        )}
        {run.step_logs.map((log) => {
          const logStatusColor =
            STATUS_COLORS[log.status] ?? "bg-gray-100 text-gray-800";
          return (
            <div
              key={log.id}
              className="border rounded p-3 bg-white text-sm"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-1.5 py-0.5 text-xs rounded ${logStatusColor}`}
                  >
                    {log.status}
                  </span>
                  <span className="text-gray-600 font-mono text-xs">
                    {log.step_id.slice(0, 8)}
                  </span>
                </div>
                <div className="flex gap-3 text-xs text-gray-500">
                  {log.records_in != null && (
                    <span>In: {log.records_in.toLocaleString()}</span>
                  )}
                  {log.records_out != null && (
                    <span>Out: {log.records_out.toLocaleString()}</span>
                  )}
                </div>
              </div>
              {log.log_output && (
                <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-x-auto whitespace-pre-wrap text-gray-600">
                  {log.log_output}
                </pre>
              )}
              <div className="mt-1 flex gap-3 text-xs text-gray-400">
                {log.started_at && (
                  <span>
                    Started: {new Date(log.started_at).toLocaleTimeString()}
                  </span>
                )}
                {log.completed_at && (
                  <span>
                    Done: {new Date(log.completed_at).toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
