"use client";

import { useCallback, useEffect, useState } from "react";

interface DCAConfig {
  id: string;
  line_item_id: string;
  read_driver_line_item_id: string | null;
  write_driver_line_item_id: string | null;
  created_at: string;
  updated_at: string;
}

interface Props {
  lineItemId: string;
  token: string;
}

export default function DCAConfigEditor({ lineItemId, token }: Props) {
  const [config, setConfig] = useState<DCAConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [readDriverId, setReadDriverId] = useState("");
  const [writeDriverId, setWriteDriverId] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const authHeaders = useCallback(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token]
  );

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/line-items/${lineItemId}/dca`, {
        headers: authHeaders(),
      });
      if (resp.status === 404) {
        setConfig(null);
        setReadDriverId("");
        setWriteDriverId("");
        return;
      }
      if (!resp.ok) throw new Error(`Failed to load DCA config (${resp.status})`);
      const data: DCAConfig = await resp.json();
      setConfig(data);
      setReadDriverId(data.read_driver_line_item_id || "");
      setWriteDriverId(data.write_driver_line_item_id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [lineItemId, authHeaders]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = useCallback(async () => {
    setSaveError(null);
    setSaveSuccess(false);
    setSaving(true);
    try {
      const resp = await fetch(`/api/line-items/${lineItemId}/dca`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          read_driver_line_item_id: readDriverId.trim() || null,
          write_driver_line_item_id: writeDriverId.trim() || null,
        }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setSaveSuccess(true);
      await fetchConfig();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save DCA config");
    } finally {
      setSaving(false);
    }
  }, [lineItemId, readDriverId, writeDriverId, authHeaders, fetchConfig]);

  const handleRemove = useCallback(async () => {
    setSaveError(null);
    setSaving(true);
    try {
      const resp = await fetch(`/api/line-items/${lineItemId}/dca`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!resp.ok && resp.status !== 404) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }
      setConfig(null);
      setReadDriverId("");
      setWriteDriverId("");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to remove DCA config");
    } finally {
      setSaving(false);
    }
  }, [lineItemId, authHeaders]);

  if (loading) {
    return <p className="text-sm text-zinc-400 py-4 text-center">Loading DCA config...</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-zinc-900">Dynamic Cell Access (DCA)</h2>
      <p className="text-sm text-zinc-500">
        Configure driver line items whose boolean values control read and write access at cell level.
      </p>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-4">
        <div className="flex flex-col gap-3">
          <div>
            <label className="block text-xs text-zinc-500 mb-1">
              Read Driver Line Item ID
            </label>
            <input
              type="text"
              value={readDriverId}
              onChange={(e) => {
                setReadDriverId(e.target.value);
                setSaveSuccess(false);
              }}
              placeholder="UUID of boolean line item (leave empty for no read restriction)"
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
              disabled={saving}
            />
            <p className="mt-1 text-xs text-zinc-400">
              When this driver evaluates to False for a cell, read access is denied.
            </p>
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1">
              Write Driver Line Item ID
            </label>
            <input
              type="text"
              value={writeDriverId}
              onChange={(e) => {
                setWriteDriverId(e.target.value);
                setSaveSuccess(false);
              }}
              placeholder="UUID of boolean line item (leave empty for no write restriction)"
              className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:border-violet-500 focus:ring-violet-200"
              disabled={saving}
            />
            <p className="mt-1 text-xs text-zinc-400">
              When this driver evaluates to False for a cell, write access is denied.
            </p>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : config ? "Update Config" : "Create Config"}
            </button>
            {config && (
              <button
                type="button"
                onClick={handleRemove}
                disabled={saving}
                className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
              >
                Remove DCA
              </button>
            )}
          </div>

          {saveError && <p className="text-xs text-red-600">{saveError}</p>}
          {saveSuccess && (
            <p className="text-xs text-green-600">DCA configuration saved successfully.</p>
          )}
        </div>
      </div>

      {config && (
        <div className="rounded-lg border border-zinc-200 p-4">
          <h3 className="text-sm font-medium text-zinc-700 mb-2">Current Configuration</h3>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-zinc-500">Read Driver:</dt>
            <dd className="text-zinc-900 font-mono text-xs">
              {config.read_driver_line_item_id || "Not set"}
            </dd>
            <dt className="text-zinc-500">Write Driver:</dt>
            <dd className="text-zinc-900 font-mono text-xs">
              {config.write_driver_line_item_id || "Not set"}
            </dd>
            <dt className="text-zinc-500">Last Updated:</dt>
            <dd className="text-zinc-900 text-xs">
              {new Date(config.updated_at).toLocaleString()}
            </dd>
          </dl>
        </div>
      )}
    </div>
  );
}
