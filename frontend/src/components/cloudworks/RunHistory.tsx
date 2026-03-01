"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RunStatus = "pending" | "running" | "completed" | "failed" | "retrying";

interface Run {
  id: string;
  schedule_id: string;
  status: RunStatus;
  attempt_number: number;
  records_processed: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface RunHistoryProps {
  scheduleId: string;
}

const STATUS_STYLES: Record<RunStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  retrying: "bg-orange-100 text-orange-800",
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "--";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function RunHistory({ scheduleId }: RunHistoryProps) {
  const { token } = useAuth();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRuns = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/schedules/${scheduleId}/runs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load run history");
        return;
      }
      const data = (await res.json()) as Run[];
      setRuns(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, scheduleId]);

  useEffect(() => {
    void fetchRuns();
  }, [fetchRuns]);

  const handleRetry = useCallback(
    async (runId: string) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/runs/${runId}/retry`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          void fetchRuns();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchRuns],
  );

  if (loading) {
    return <div className="p-4 text-gray-500">Loading run history...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Run History</h2>
        <button
          onClick={() => fetchRuns()}
          className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      {runs.length === 0 ? (
        <p className="text-sm text-gray-500">No runs recorded yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Status</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Attempt</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Records</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Started</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Completed</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Error</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="whitespace-nowrap px-3 py-2">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        STATUS_STYLES[run.status]
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{run.attempt_number}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {run.records_processed !== null ? run.records_processed.toLocaleString() : "--"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">{formatDateTime(run.started_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {formatDateTime(run.completed_at)}
                  </td>
                  <td className="max-w-xs truncate px-3 py-2 text-red-600" title={run.error_message ?? undefined}>
                    {run.error_message ?? "--"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {run.status === "failed" && (
                      <button
                        onClick={() => handleRetry(run.id)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
