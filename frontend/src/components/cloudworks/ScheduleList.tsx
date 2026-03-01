"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ScheduleType = "import" | "export";

interface Schedule {
  id: string;
  connection_id: string;
  name: string;
  description: string | null;
  schedule_type: ScheduleType;
  cron_expression: string;
  source_config: Record<string, unknown> | null;
  target_config: Record<string, unknown> | null;
  is_enabled: boolean;
  max_retries: number;
  retry_delay_seconds: number;
  created_at: string;
  updated_at: string;
}

interface ScheduleListProps {
  connectionId: string;
  onSelectSchedule?: (scheduleId: string) => void;
}

export function ScheduleList({ connectionId, onSelectSchedule }: ScheduleListProps) {
  const { token } = useAuth();
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<ScheduleType>("import");
  const [newCron, setNewCron] = useState("0 0 * * *");
  const [creating, setCreating] = useState(false);

  const fetchSchedules = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/connections/${connectionId}/schedules`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load schedules");
        return;
      }
      const data = (await res.json()) as Schedule[];
      setSchedules(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, connectionId]);

  useEffect(() => {
    void fetchSchedules();
  }, [fetchSchedules]);

  const handleCreate = useCallback(async () => {
    if (!token || !newName.trim()) return;
    setCreating(true);
    try {
      const res = await fetch(`${API_BASE}/connections/${connectionId}/schedules`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newName.trim(),
          schedule_type: newType,
          cron_expression: newCron,
        }),
      });
      if (res.ok) {
        setNewName("");
        setShowCreate(false);
        void fetchSchedules();
      }
    } catch {
      // Silently ignore
    } finally {
      setCreating(false);
    }
  }, [token, connectionId, newName, newType, newCron, fetchSchedules]);

  const handleToggleEnabled = useCallback(
    async (schedule: Schedule) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/schedules/${schedule.id}/enable`, {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ is_enabled: !schedule.is_enabled }),
        });
        if (res.ok) {
          void fetchSchedules();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchSchedules],
  );

  const handleTrigger = useCallback(
    async (scheduleId: string) => {
      if (!token) return;
      try {
        await fetch(`${API_BASE}/schedules/${scheduleId}/trigger`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // Silently ignore
      }
    },
    [token],
  );

  const handleDelete = useCallback(
    async (scheduleId: string) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/schedules/${scheduleId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          void fetchSchedules();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchSchedules],
  );

  if (loading) {
    return <div className="p-4 text-gray-500">Loading schedules...</div>;
  }

  if (error) {
    return <div className="p-4 text-red-500">{error}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Schedules</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          {showCreate ? "Cancel" : "New Schedule"}
        </button>
      </div>

      {showCreate && (
        <div className="rounded border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700">Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 block w-full rounded border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
              placeholder="Schedule name"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Type</label>
            <select
              value={newType}
              onChange={(e) => setNewType(e.target.value as ScheduleType)}
              className="mt-1 block w-full rounded border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="import">Import</option>
              <option value="export">Export</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Cron Expression</label>
            <input
              type="text"
              value={newCron}
              onChange={(e) => setNewCron(e.target.value)}
              className="mt-1 block w-full rounded border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
              placeholder="0 0 * * *"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={creating || !newName.trim()}
            className="rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            {creating ? "Creating..." : "Create"}
          </button>
        </div>
      )}

      {schedules.length === 0 ? (
        <p className="text-sm text-gray-500">No schedules configured yet.</p>
      ) : (
        <div className="divide-y divide-gray-200 rounded border border-gray-200">
          {schedules.map((sched) => (
            <div key={sched.id} className="p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onSelectSchedule?.(sched.id)}
                    className="font-medium hover:underline"
                  >
                    {sched.name}
                  </button>
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      sched.schedule_type === "import"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-purple-100 text-purple-700"
                    }`}
                  >
                    {sched.schedule_type}
                  </span>
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      sched.is_enabled ? "bg-green-500" : "bg-gray-400"
                    }`}
                    title={sched.is_enabled ? "Enabled" : "Disabled"}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleTrigger(sched.id)}
                    className="text-xs text-green-600 hover:underline"
                  >
                    Trigger
                  </button>
                  <button
                    onClick={() => handleToggleEnabled(sched)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {sched.is_enabled ? "Disable" : "Enable"}
                  </button>
                  <button
                    onClick={() => handleDelete(sched.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <div className="mt-1 text-xs text-gray-500">
                Cron: <code className="rounded bg-gray-100 px-1">{sched.cron_expression}</code>
                {" | "}Max retries: {sched.max_retries}
                {" | "}Retry delay: {sched.retry_delay_seconds}s
              </div>
              {sched.description && (
                <div className="mt-1 text-xs text-gray-500">{sched.description}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
