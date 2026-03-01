"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Metric {
  id: string;
  profile_id: string;
  metric_name: string;
  metric_value: number;
  measured_at: string;
  metadata_json: Record<string, unknown> | null;
}

interface MetricsDashboardProps {
  modelId: string;
}

export function MetricsDashboard({ modelId }: MetricsDashboardProps) {
  const { token } = useAuth();
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Record metric form
  const [metricName, setMetricName] = useState("");
  const [metricValue, setMetricValue] = useState("");
  const [recording, setRecording] = useState(false);

  const fetchMetrics = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile/metrics`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        setMetrics((await res.json()) as Metric[]);
        setError(null);
      } else if (res.status === 404) {
        setMetrics([]);
        setError("No engine profile configured for this model.");
      }
    } catch {
      setError("Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, [token, modelId]);

  useEffect(() => {
    void fetchMetrics();
  }, [fetchMetrics]);

  const handleRecord = async () => {
    if (!token || !metricName || !metricValue) return;
    setRecording(true);
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile/metrics`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            metric_name: metricName,
            metric_value: parseFloat(metricValue),
          }),
        }
      );
      if (res.ok) {
        setMetricName("");
        setMetricValue("");
        void fetchMetrics();
      }
    } catch {
      setError("Failed to record metric");
    } finally {
      setRecording(false);
    }
  };

  // Group metrics by name for summary
  const grouped: Record<string, Metric[]> = {};
  for (const m of metrics) {
    if (!grouped[m.metric_name]) {
      grouped[m.metric_name] = [];
    }
    grouped[m.metric_name].push(m);
  }

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">Loading metrics...</div>;
  }

  return (
    <div className="space-y-6 rounded-lg border p-6">
      <h2 className="text-lg font-semibold">Performance Metrics</h2>

      {error && (
        <div className="rounded bg-yellow-50 p-3 text-sm text-yellow-700">
          {error}
        </div>
      )}

      {/* Summary cards */}
      {Object.keys(grouped).length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(grouped).map(([name, items]) => {
            const latest = items[0];
            const avg =
              items.reduce((s, m) => s + m.metric_value, 0) / items.length;
            return (
              <div key={name} className="rounded border p-4">
                <div className="text-xs font-medium uppercase text-gray-500">
                  {name}
                </div>
                <div className="mt-1 text-2xl font-bold">
                  {latest.metric_value.toLocaleString()}
                </div>
                <div className="text-xs text-gray-400">
                  Avg: {avg.toFixed(1)} | {items.length} readings
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Metric history table */}
      {metrics.length > 0 && (
        <div className="overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-gray-500">
              <tr>
                <th className="py-2 pr-4">Metric</th>
                <th className="py-2 pr-4">Value</th>
                <th className="py-2 pr-4">Measured At</th>
                <th className="py-2">Metadata</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m.id} className="border-b">
                  <td className="py-2 pr-4 font-medium">{m.metric_name}</td>
                  <td className="py-2 pr-4">
                    {m.metric_value.toLocaleString()}
                  </td>
                  <td className="py-2 pr-4 text-gray-500">
                    {new Date(m.measured_at).toLocaleString()}
                  </td>
                  <td className="py-2 text-xs text-gray-400">
                    {m.metadata_json
                      ? JSON.stringify(m.metadata_json)
                      : "--"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Record new metric */}
      <div className="border-t pt-4">
        <h3 className="mb-2 text-sm font-medium">Record Metric</h3>
        <div className="flex gap-3">
          <input
            placeholder="Metric name"
            value={metricName}
            onChange={(e) => setMetricName(e.target.value)}
            className="rounded border px-3 py-2 text-sm"
          />
          <input
            placeholder="Value"
            type="number"
            value={metricValue}
            onChange={(e) => setMetricValue(e.target.value)}
            className="w-32 rounded border px-3 py-2 text-sm"
          />
          <button
            onClick={handleRecord}
            disabled={recording || !metricName || !metricValue}
            className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            {recording ? "Recording..." : "Record"}
          </button>
        </div>
      </div>
    </div>
  );
}
