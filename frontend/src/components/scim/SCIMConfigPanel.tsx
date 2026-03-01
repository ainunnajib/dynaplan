"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SCIMConfig {
  id: string;
  workspace_id: string;
  is_enabled: boolean;
  base_url: string;
  created_at: string;
  updated_at: string;
}

interface SCIMConfigPanelProps {
  workspaceId: string;
  token: string;
  apiBase?: string;
}

type FormState = {
  bearer_token: string;
  base_url: string;
  is_enabled: boolean;
};

const DEFAULT_FORM: FormState = {
  bearer_token: "",
  base_url: "http://localhost:8000",
  is_enabled: true,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SCIMConfigPanel({
  workspaceId,
  token,
  apiBase = "http://localhost:8000",
}: SCIMConfigPanelProps) {
  const [config, setConfig] = useState<SCIMConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [generatedToken, setGeneratedToken] = useState<string | null>(null);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${apiBase}/workspaces/${workspaceId}/scim/config`,
        { headers }
      );
      if (resp.status === 404) {
        setConfig(null);
        setForm(DEFAULT_FORM);
      } else if (!resp.ok) {
        throw new Error(`Failed to load SCIM config: ${resp.statusText}`);
      } else {
        const data: SCIMConfig = await resp.json();
        setConfig(data);
        setForm({
          bearer_token: "",
          base_url: data.base_url,
          is_enabled: data.is_enabled,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, token, apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  function handleChange(
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) {
    const { name, value, type } = e.target;
    const checked =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : undefined;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  function generateToken() {
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const tok = Array.from(array, (b) => b.toString(16).padStart(2, "0")).join(
      ""
    );
    setForm((prev) => ({ ...prev, bearer_token: tok }));
    setGeneratedToken(tok);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      let resp: Response;
      if (config) {
        const payload: Record<string, unknown> = {
          is_enabled: form.is_enabled,
          base_url: form.base_url,
        };
        if (form.bearer_token) {
          payload.bearer_token = form.bearer_token;
        }
        resp = await fetch(
          `${apiBase}/workspaces/${workspaceId}/scim/config`,
          {
            method: "PUT",
            headers,
            body: JSON.stringify(payload),
          }
        );
      } else {
        if (!form.bearer_token) {
          setError("Bearer token is required when creating a new SCIM config.");
          setSaving(false);
          return;
        }
        resp = await fetch(
          `${apiBase}/workspaces/${workspaceId}/scim/config`,
          {
            method: "POST",
            headers,
            body: JSON.stringify({
              bearer_token: form.bearer_token,
              base_url: form.base_url,
              is_enabled: form.is_enabled,
            }),
          }
        );
      }
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail ?? `Save failed: ${resp.statusText}`);
      }
      const data: SCIMConfig = await resp.json();
      setConfig(data);
      setForm((prev) => ({ ...prev, bearer_token: "" }));
      setSuccess(
        config ? "SCIM configuration updated." : "SCIM provisioning enabled."
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-zinc-400 text-sm">
        Loading SCIM configuration...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">
            SCIM Provisioning
          </h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {config
              ? "Manage your SCIM provisioning settings."
              : "Enable SCIM to auto-provision users and groups from your identity provider."}
          </p>
        </div>
        {config && (
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              config.is_enabled
                ? "bg-green-100 text-green-700"
                : "bg-zinc-100 text-zinc-500"
            }`}
          >
            {config.is_enabled ? "Enabled" : "Disabled"}
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      {generatedToken && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p className="font-medium">
            Save this bearer token - it will not be shown again:
          </p>
          <code className="mt-1 block break-all text-xs font-mono bg-amber-100 px-2 py-1 rounded">
            {generatedToken}
          </code>
        </div>
      )}

      <form onSubmit={handleSave} className="flex flex-col gap-5">
        {/* Bearer Token */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">
            Bearer Token{" "}
            {config && (
              <span className="font-normal text-zinc-400">
                (leave blank to keep existing)
              </span>
            )}
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              name="bearer_token"
              value={form.bearer_token}
              onChange={handleChange}
              placeholder={config ? "Enter new token to rotate" : "Enter or generate a token"}
              className="flex-1 rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400 font-mono"
            />
            <button
              type="button"
              onClick={generateToken}
              className="rounded-md border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors whitespace-nowrap"
            >
              Generate
            </button>
          </div>
          <p className="text-xs text-zinc-500">
            This token will be used by your IdP to authenticate SCIM requests.
          </p>
        </div>

        {/* Base URL */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Base URL</label>
          <input
            type="url"
            name="base_url"
            value={form.base_url}
            onChange={handleChange}
            placeholder="https://your-dynaplan-instance.com"
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
          <p className="text-xs text-zinc-500">
            The SCIM endpoint URL your IdP will use:{" "}
            <code className="bg-zinc-100 px-1 rounded">{form.base_url}/scim/v2</code>
          </p>
        </div>

        {/* Enabled */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="is_enabled"
            name="is_enabled"
            checked={form.is_enabled}
            onChange={handleChange}
            className="h-4 w-4 rounded border-zinc-300 text-violet-600 focus:ring-violet-400"
          />
          <div>
            <label
              htmlFor="is_enabled"
              className="text-sm font-medium text-zinc-700 cursor-pointer"
            >
              Enable SCIM provisioning
            </label>
            <p className="text-xs text-zinc-500">
              When disabled, the IdP will not be able to create or update users.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {saving
              ? "Saving..."
              : config
              ? "Update Configuration"
              : "Enable SCIM"}
          </button>
        </div>
      </form>
    </div>
  );
}
