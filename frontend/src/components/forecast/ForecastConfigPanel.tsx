"use client";

import { useState, type FormEvent, useEffect } from "react";
import { fetchApi } from "@/lib/api";

interface Version {
  id: string;
  name: string;
  version_type: string;
}

interface ForecastConfig {
  id: string;
  model_id: string;
  forecast_horizon_months: number;
  auto_archive: boolean;
  archive_actuals_version_id: string | null;
  forecast_version_id: string | null;
  last_rolled_at: string | null;
  created_at: string;
  updated_at: string;
}

interface ForecastConfigPanelProps {
  modelId: string;
  versions: Version[];
  /** Called after a config is successfully saved. */
  onSaved?: (config: ForecastConfig) => void;
}

export default function ForecastConfigPanel({
  modelId,
  versions,
  onSaved,
}: ForecastConfigPanelProps) {
  const [horizonMonths, setHorizonMonths] = useState(12);
  const [autoArchive, setAutoArchive] = useState(true);
  const [actualsVersionId, setActualsVersionId] = useState("");
  const [forecastVersionId, setForecastVersionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [existingConfig, setExistingConfig] = useState<ForecastConfig | null>(null);

  const actualsVersions = versions.filter((v) => v.version_type === "actuals");
  const forecastVersions = versions.filter((v) => v.version_type === "forecast");

  useEffect(() => {
    async function loadConfig() {
      setIsLoading(true);
      try {
        const config = await fetchApi<ForecastConfig>(
          `/api/models/${modelId}/forecast-config`
        );
        setExistingConfig(config);
        setHorizonMonths(config.forecast_horizon_months);
        setAutoArchive(config.auto_archive);
        setActualsVersionId(config.archive_actuals_version_id ?? "");
        setForecastVersionId(config.forecast_version_id ?? "");
      } catch {
        // Config does not exist yet — that is fine
        setExistingConfig(null);
      } finally {
        setIsLoading(false);
      }
    }
    loadConfig();
  }, [modelId]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    const payload = {
      model_id: modelId,
      forecast_horizon_months: horizonMonths,
      auto_archive: autoArchive,
      actuals_version_id: actualsVersionId || null,
      forecast_version_id: forecastVersionId || null,
    };

    try {
      let saved: ForecastConfig;
      if (existingConfig) {
        saved = await fetchApi<ForecastConfig>(
          `/api/models/${modelId}/forecast-config`,
          { method: "PATCH", body: JSON.stringify(payload) }
        );
      } else {
        saved = await fetchApi<ForecastConfig>(
          `/api/models/${modelId}/forecast-config`,
          { method: "POST", body: JSON.stringify(payload) }
        );
        setExistingConfig(saved);
      }
      setSuccessMessage("Forecast configuration saved successfully.");
      onSaved?.(saved);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save forecast configuration."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-6">
        <p className="text-sm text-zinc-500">Loading forecast configuration...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-base font-semibold text-zinc-900">
        Forecast Configuration
      </h2>
      <p className="mb-5 text-sm text-zinc-500">
        Configure the rolling forecast horizon and version mappings.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Horizon months */}
        <div>
          <label
            htmlFor="horizon-months"
            className="block text-sm font-medium text-zinc-700"
          >
            Forecast Horizon (months)
          </label>
          <input
            id="horizon-months"
            type="number"
            min={1}
            max={120}
            value={horizonMonths}
            onChange={(e) => setHorizonMonths(Number(e.target.value))}
            disabled={isSubmitting}
            className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-zinc-400">
            How many months ahead the forecast should extend.
          </p>
        </div>

        {/* Auto-archive toggle */}
        <div className="flex items-start gap-3">
          <input
            id="auto-archive"
            type="checkbox"
            checked={autoArchive}
            onChange={(e) => setAutoArchive(e.target.checked)}
            disabled={isSubmitting}
            className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
          />
          <div>
            <label
              htmlFor="auto-archive"
              className="block text-sm font-medium text-zinc-700"
            >
              Auto-archive past periods to actuals
            </label>
            <p className="text-xs text-zinc-400">
              When rolling forward, copy forecast cell values into the actuals version.
            </p>
          </div>
        </div>

        {/* Actuals version selector */}
        <div>
          <label
            htmlFor="actuals-version"
            className="block text-sm font-medium text-zinc-700"
          >
            Actuals Version
          </label>
          <select
            id="actuals-version"
            value={actualsVersionId}
            onChange={(e) => setActualsVersionId(e.target.value)}
            disabled={isSubmitting}
            className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          >
            <option value="">-- None --</option>
            {actualsVersions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-zinc-400">
            The version where archived forecast data will be stored.
          </p>
        </div>

        {/* Forecast version selector */}
        <div>
          <label
            htmlFor="forecast-version"
            className="block text-sm font-medium text-zinc-700"
          >
            Forecast Version
          </label>
          <select
            id="forecast-version"
            value={forecastVersionId}
            onChange={(e) => setForecastVersionId(e.target.value)}
            disabled={isSubmitting}
            className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          >
            <option value="">-- None --</option>
            {forecastVersions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-zinc-400">
            The forecast version whose switchover period will be advanced on roll.
          </p>
        </div>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
            {error}
          </p>
        )}

        {successMessage && (
          <p className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
            {successMessage}
          </p>
        )}

        <div className="flex justify-end pt-1">
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Saving..." : existingConfig ? "Update Configuration" : "Save Configuration"}
          </button>
        </div>
      </form>
    </div>
  );
}
