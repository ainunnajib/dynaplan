"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getObservabilityDashboard,
  getGrafanaTemplate,
  type ObservabilityDashboard,
} from "@/lib/api";

interface HealthDashboardProps {
  modelId?: string;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export default function HealthDashboard({ modelId }: HealthDashboardProps) {
  const [dashboard, setDashboard] = useState<ObservabilityDashboard | null>(null);
  const [grafanaTitle, setGrafanaTitle] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [dashboardData, template] = await Promise.all([
        getObservabilityDashboard(modelId),
        getGrafanaTemplate(),
      ]);
      setDashboard(dashboardData);
      setGrafanaTitle(template.title);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load observability data");
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => {
      void load();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [load]);

  const healthStyle = useMemo(() => {
    if (dashboard?.health_status === "ok") {
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    }
    return "bg-amber-50 text-amber-700 border-amber-200";
  }, [dashboard?.health_status]);

  if (loading) {
    return (
      <section className="rounded-lg border border-zinc-200 bg-white p-6">
        <h2 className="text-base font-semibold text-zinc-900">Metrics &amp; Health Dashboard</h2>
        <p className="mt-2 text-sm text-zinc-500">Loading observability metrics...</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold text-zinc-900">Metrics &amp; Health Dashboard</h2>
        {dashboard && (
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${healthStyle}`}
          >
            {dashboard.health_status === "ok" ? "Healthy" : "Degraded"}
          </span>
        )}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {dashboard && (
        <>
          <p className="mt-2 text-xs text-zinc-500">
            Updated {new Date(dashboard.generated_at).toLocaleString()} • Grafana template: {grafanaTitle ?? "N/A"}
          </p>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="API Avg Latency" value={`${formatNumber(dashboard.api.request_latency_ms_avg)} ms`} />
            <MetricCard label="API Error Rate" value={formatPercent(dashboard.api.error_rate)} />
            <MetricCard label="Active Users" value={formatNumber(dashboard.api.active_users)} />
            <MetricCard
              label="CloudWorks Success"
              value={formatPercent(dashboard.integration.cloudworks_run_success_rate)}
            />
          </div>

          <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-md border border-zinc-200 p-4">
              <h3 className="text-sm font-semibold text-zinc-800">API Metrics</h3>
              <dl className="mt-3 space-y-2 text-sm text-zinc-700">
                <MetricRow label="Requests (total)" value={formatNumber(dashboard.api.requests_total)} />
                <MetricRow label="Requests (last 5m)" value={formatNumber(dashboard.api.requests_last_5m)} />
                <MetricRow
                  label="Avg latency (last 5m)"
                  value={`${formatNumber(dashboard.api.request_latency_ms_avg_last_5m)} ms`}
                />
                <MetricRow label="Error rate (last 5m)" value={formatPercent(dashboard.api.error_rate_last_5m)} />
                <MetricRow label="In-flight requests" value={formatNumber(dashboard.api.in_flight_requests)} />
              </dl>
            </div>

            <div className="rounded-md border border-zinc-200 p-4">
              <h3 className="text-sm font-semibold text-zinc-800">Integration Metrics</h3>
              <dl className="mt-3 space-y-2 text-sm text-zinc-700">
                <MetricRow
                  label="CloudWorks runs"
                  value={formatNumber(dashboard.integration.cloudworks_runs_total)}
                />
                <MetricRow
                  label="Pipeline runs"
                  value={formatNumber(dashboard.integration.pipeline_runs_total)}
                />
                <MetricRow
                  label="Pipeline throughput"
                  value={`${formatNumber(dashboard.integration.pipeline_throughput_records_per_minute)} rec/min`}
                />
              </dl>
            </div>
          </div>

          <div className="mt-5 overflow-x-auto rounded-md border border-zinc-200">
            <table className="min-w-full divide-y divide-zinc-200 text-sm">
              <thead className="bg-zinc-50 text-xs uppercase text-zinc-500">
                <tr>
                  <th className="px-3 py-2 text-left">Model</th>
                  <th className="px-3 py-2 text-right">Calc Avg (ms)</th>
                  <th className="px-3 py-2 text-right">Calc Latest (ms)</th>
                  <th className="px-3 py-2 text-right">Cache Hit Ratio</th>
                  <th className="px-3 py-2 text-right">Memory (MB)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 bg-white text-zinc-700">
                {dashboard.engine.models.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-4 text-center text-zinc-500">
                      No engine metrics recorded yet.
                    </td>
                  </tr>
                ) : (
                  dashboard.engine.models.map((modelMetrics) => (
                    <tr key={modelMetrics.model_id}>
                      <td className="px-3 py-2 font-mono text-xs text-zinc-600">{modelMetrics.model_id}</td>
                      <td className="px-3 py-2 text-right">
                        {modelMetrics.calc_time_ms_avg == null
                          ? "--"
                          : formatNumber(modelMetrics.calc_time_ms_avg)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {modelMetrics.calc_time_ms_latest == null
                          ? "--"
                          : formatNumber(modelMetrics.calc_time_ms_latest)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {modelMetrics.cache_hit_ratio == null
                          ? "--"
                          : formatPercent(modelMetrics.cache_hit_ratio)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        {modelMetrics.memory_usage_mb == null
                          ? "--"
                          : formatNumber(modelMetrics.memory_usage_mb)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-5 rounded-md border border-zinc-200 p-4">
            <h3 className="text-sm font-semibold text-zinc-800">Health Checks</h3>
            <ul className="mt-3 space-y-2 text-sm">
              {dashboard.checks.map((check) => (
                <li key={check.name} className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-zinc-800">{check.name}</p>
                    <p className="text-zinc-500">{check.detail}</p>
                  </div>
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      check.status === "ok"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {check.status}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-zinc-900">{value}</p>
    </div>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-medium text-zinc-800">{value}</dd>
    </div>
  );
}
