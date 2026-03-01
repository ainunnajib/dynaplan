"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface ImportTask {
  id: string;
  upload_id: string | null;
  model_id: string;
  task_type: string;
  target_id: string;
  status: string;
  total_records: number | null;
  processed_records: number;
  error_count: number;
  errors: Record<string, unknown> | null;
  created_at: string;
  completed_at: string | null;
}

interface ImportTaskMonitorProps {
  modelId: string;
  taskId?: string;
  pollIntervalMs?: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiFetch(path: string) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    validating: "bg-blue-100 text-blue-800",
    importing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        colors[status] || "bg-gray-100 text-gray-800"
      }`}
    >
      {status}
    </span>
  );
}

function taskTypeLabel(taskType: string): string {
  const labels: Record<string, string> = {
    list_import: "List Import",
    module_import: "Module Import",
    cell_import: "Cell Import",
  };
  return labels[taskType] || taskType;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ImportTaskMonitor({
  modelId,
  taskId,
  pollIntervalMs = 3000,
}: ImportTaskMonitorProps) {
  const [tasks, setTasks] = useState<ImportTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<ImportTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    try {
      if (taskId) {
        const task: ImportTask = await apiFetch(`/import-tasks/${taskId}`);
        setSelectedTask(task);
        setTasks([task]);
      } else {
        const list: ImportTask[] = await apiFetch(
          `/models/${modelId}/import-tasks`
        );
        setTasks(list);
        if (list.length > 0 && !selectedTask) {
          setSelectedTask(list[0]);
        }
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch tasks");
    } finally {
      setLoading(false);
    }
  }, [modelId, taskId, selectedTask]);

  // Poll for active tasks
  useEffect(() => {
    fetchTasks();

    const hasActive = tasks.some(
      (t) => t.status === "pending" || t.status === "validating" || t.status === "importing"
    );

    if (hasActive) {
      const interval = setInterval(fetchTasks, pollIntervalMs);
      return () => clearInterval(interval);
    }
  }, [fetchTasks, tasks, pollIntervalMs]);

  if (loading) {
    return (
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <p className="text-sm text-gray-500">Loading import tasks...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Import Tasks
      </h3>

      {tasks.length === 0 ? (
        <p className="text-sm text-gray-500">No import tasks found.</p>
      ) : (
        <div className="space-y-4">
          {/* Task list */}
          <div className="divide-y rounded-md border">
            {tasks.map((task) => (
              <button
                key={task.id}
                onClick={() => setSelectedTask(task)}
                className={`flex w-full items-center justify-between px-4 py-3 text-left hover:bg-gray-50 ${
                  selectedTask?.id === task.id ? "bg-blue-50" : ""
                }`}
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {taskTypeLabel(task.task_type)}
                  </p>
                  <p className="text-xs text-gray-500">
                    {new Date(task.created_at).toLocaleString()}
                  </p>
                </div>
                {statusBadge(task.status)}
              </button>
            ))}
          </div>

          {/* Selected task detail */}
          {selectedTask && (
            <div className="rounded-md border bg-gray-50 p-4">
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-gray-800">
                  {taskTypeLabel(selectedTask.task_type)}
                </h4>
                {statusBadge(selectedTask.status)}
              </div>

              {/* Progress bar */}
              {selectedTask.total_records != null &&
                selectedTask.total_records > 0 && (
                  <div className="mb-3">
                    <div className="mb-1 flex justify-between text-xs text-gray-600">
                      <span>
                        {selectedTask.processed_records} /{" "}
                        {selectedTask.total_records} records
                      </span>
                      <span>
                        {Math.round(
                          (selectedTask.processed_records /
                            selectedTask.total_records) *
                            100
                        )}
                        %
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-200">
                      <div
                        className="h-2 rounded-full bg-blue-600 transition-all duration-300"
                        style={{
                          width: `${Math.round(
                            (selectedTask.processed_records /
                              selectedTask.total_records) *
                              100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <dt className="text-gray-500">Task ID</dt>
                  <dd className="font-mono text-gray-700">
                    {selectedTask.id.slice(0, 8)}...
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">Target</dt>
                  <dd className="font-mono text-gray-700">
                    {selectedTask.target_id.slice(0, 8)}...
                  </dd>
                </div>
                <div>
                  <dt className="text-gray-500">Errors</dt>
                  <dd className="text-gray-700">{selectedTask.error_count}</dd>
                </div>
                {selectedTask.completed_at && (
                  <div>
                    <dt className="text-gray-500">Completed</dt>
                    <dd className="text-gray-700">
                      {new Date(selectedTask.completed_at).toLocaleString()}
                    </dd>
                  </div>
                )}
              </dl>

              {selectedTask.errors && (
                <div className="mt-3 rounded bg-red-50 p-2">
                  <p className="text-xs font-medium text-red-800">Errors:</p>
                  <pre className="mt-1 max-h-32 overflow-auto text-xs text-red-700">
                    {JSON.stringify(selectedTask.errors, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
