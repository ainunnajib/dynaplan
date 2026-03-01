"use client";

import { useEffect, useState } from "react";
import BulkWriteForm from "./BulkWriteForm";
import JobProgress from "./JobProgress";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

type ActivePanel = "none" | "write" | "delete" | "copy";

interface BulkJob {
  id: string;
  job_type: string;
  status: string;
  processed_rows: number;
  total_rows: number | null;
  failed_rows: number;
  created_at: string;
}

interface BulkOperationsPanelProps {
  modelId: string;
}

// ── Action card ───────────────────────────────────────────────────────────────

interface ActionCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  onClick: () => void;
  active: boolean;
}

function ActionCard({ title, description, icon, onClick, active }: ActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "flex flex-col items-start rounded-xl border p-4 text-left transition-all w-full",
        active
          ? "border-blue-400 bg-blue-50 shadow-sm"
          : "border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-50",
      ].join(" ")}
    >
      <div className="mb-2 rounded-lg bg-blue-100 p-2 text-blue-600">
        {icon}
      </div>
      <p className="text-sm font-semibold text-zinc-800">{title}</p>
      <p className="mt-0.5 text-xs text-zinc-500">{description}</p>
    </button>
  );
}

// ── Jobs list ─────────────────────────────────────────────────────────────────

function JobStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: "bg-zinc-100 text-zinc-600",
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-600",
    cancelled: "bg-orange-100 text-orange-600",
  };
  const cls = styles[status] ?? "bg-zinc-100 text-zinc-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${cls}`}>
      {status}
    </span>
  );
}

// ── Delete form ────────────────────────────────────────────────────────────────

interface DeleteFormProps {
  modelId: string;
  onJobCreated: (jobId: string) => void;
}

function BulkDeleteForm({ modelId, onJobCreated }: DeleteFormProps) {
  const [lineItemId, setLineItemId] = useState("");
  const [dimPrefix, setDimPrefix] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    const token = getAuthToken();
    const body: Record<string, string> = {};
    if (lineItemId.trim()) body.line_item_id = lineItemId.trim();
    if (dimPrefix.trim()) body.dimension_key_prefix = dimPrefix.trim();

    try {
      const resp = await fetch(`${API_BASE_URL}/models/${modelId}/bulk/delete`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const bd = await resp.json().catch(() => ({}));
        throw new Error((bd as { detail?: string }).detail ?? `Delete failed: ${resp.status}`);
      }
      const job = await resp.json();
      onJobCreated(job.id as string);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk delete failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-600">
        Delete cells matching the criteria below. Leave fields blank to delete all cells in the model.
      </p>
      <div>
        <label className="block text-xs font-medium text-zinc-700 mb-1">
          Line item ID (optional)
        </label>
        <input
          type="text"
          value={lineItemId}
          onChange={(e) => setLineItemId(e.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-700 mb-1">
          Dimension key prefix (optional)
        </label>
        <input
          type="text"
          value={dimPrefix}
          onChange={(e) => setDimPrefix(e.target.value)}
          placeholder="xxxxxxxx-xxxx…"
          className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        />
      </div>
      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting}
        className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
      >
        {submitting ? "Deleting…" : "Delete cells"}
      </button>
    </div>
  );
}

// ── Copy form ──────────────────────────────────────────────────────────────────

interface CopyFormProps {
  onJobCreated: (jobId: string) => void;
}

function BulkCopyForm({ onJobCreated }: CopyFormProps) {
  const [sourceModelId, setSourceModelId] = useState("");
  const [targetModelId, setTargetModelId] = useState("");
  const [mappingJson, setMappingJson] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    let mapping: Record<string, string> = {};
    try {
      mapping = JSON.parse(mappingJson);
    } catch {
      setError("Invalid JSON for line item mapping");
      return;
    }

    setSubmitting(true);
    setError(null);
    const token = getAuthToken();

    try {
      const resp = await fetch(`${API_BASE_URL}/bulk/copy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          source_model_id: sourceModelId.trim(),
          target_model_id: targetModelId.trim(),
          line_item_mapping: mapping,
        }),
      });
      if (!resp.ok) {
        const bd = await resp.json().catch(() => ({}));
        throw new Error((bd as { detail?: string }).detail ?? `Copy failed: ${resp.status}`);
      }
      const job = await resp.json();
      onJobCreated(job.id as string);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bulk copy failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-zinc-700 mb-1">Source model ID</label>
        <input
          type="text"
          value={sourceModelId}
          onChange={(e) => setSourceModelId(e.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-700 mb-1">Target model ID</label>
        <input
          type="text"
          value={targetModelId}
          onChange={(e) => setTargetModelId(e.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          className="w-full rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-zinc-700 mb-1">
          Line item mapping (JSON object)
        </label>
        <textarea
          value={mappingJson}
          onChange={(e) => setMappingJson(e.target.value)}
          rows={4}
          placeholder={'{\n  "<source-li-id>": "<target-li-id>"\n}'}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-xs text-zinc-800 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none resize-y"
        />
      </div>
      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
      )}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting || !sourceModelId.trim() || !targetModelId.trim() || !mappingJson.trim()}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {submitting ? "Copying…" : "Copy model data"}
      </button>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

/**
 * BulkOperationsPanel — dashboard panel for all bulk data operations.
 *
 * Provides action cards for Bulk Write, Bulk Delete, and Copy Model Data.
 * Each card expands an inline form. Recent jobs are listed below.
 */
export default function BulkOperationsPanel({ modelId }: BulkOperationsPanelProps) {
  const [activePanel, setActivePanel] = useState<ActivePanel>("none");
  const [recentJobs, setRecentJobs] = useState<BulkJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  function togglePanel(panel: ActivePanel) {
    setActivePanel((prev) => (prev === panel ? "none" : panel));
  }

  async function loadRecentJobs() {
    const token = getAuthToken();
    if (!token) return;
    setLoadingJobs(true);
    try {
      const resp = await fetch(`${API_BASE_URL}/models/${modelId}/bulk/jobs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        const jobs: BulkJob[] = await resp.json();
        setRecentJobs(jobs.slice(0, 10));
      }
    } catch {
      // Silently ignore
    } finally {
      setLoadingJobs(false);
    }
  }

  useEffect(() => {
    loadRecentJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId]);

  function handleJobCreated(jobId: string) {
    setActiveJobId(jobId);
    // Reload jobs list after a brief delay to catch the new job
    setTimeout(() => loadRecentJobs(), 1500);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-zinc-900">Bulk Data Operations</h2>
        <p className="text-sm text-zinc-500 mt-0.5">
          Perform high-volume read, write, delete, and copy operations with progress tracking.
        </p>
      </div>

      {/* Action cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <ActionCard
          title="Bulk Write"
          description="Import large sets of cell values in chunks"
          active={activePanel === "write"}
          onClick={() => togglePanel("write")}
          icon={<WriteIcon className="h-5 w-5" />}
        />
        <ActionCard
          title="Bulk Delete"
          description="Delete cells matching criteria"
          active={activePanel === "delete"}
          onClick={() => togglePanel("delete")}
          icon={<DeleteIcon className="h-5 w-5" />}
        />
        <ActionCard
          title="Copy Model Data"
          description="Copy cells between models"
          active={activePanel === "copy"}
          onClick={() => togglePanel("copy")}
          icon={<CopyIcon className="h-5 w-5" />}
        />
      </div>

      {/* Inline forms */}
      {activePanel !== "none" && (
        <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
          {activePanel === "write" && (
            <>
              <h3 className="text-sm font-semibold text-zinc-800 mb-4">Bulk Write Cells</h3>
              <BulkWriteForm modelId={modelId} onSuccess={handleJobCreated} />
            </>
          )}
          {activePanel === "delete" && (
            <>
              <h3 className="text-sm font-semibold text-zinc-800 mb-4">Bulk Delete Cells</h3>
              <BulkDeleteForm modelId={modelId} onJobCreated={handleJobCreated} />
            </>
          )}
          {activePanel === "copy" && (
            <>
              <h3 className="text-sm font-semibold text-zinc-800 mb-4">Copy Model Data</h3>
              <BulkCopyForm onJobCreated={handleJobCreated} />
            </>
          )}
        </div>
      )}

      {/* Active job progress */}
      {activeJobId && (
        <div>
          <p className="text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wide">
            Active job
          </p>
          <JobProgress
            jobId={activeJobId}
            onFinished={() => {
              loadRecentJobs();
            }}
          />
        </div>
      )}

      {/* Recent jobs */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
            Recent jobs
          </p>
          <button
            type="button"
            onClick={loadRecentJobs}
            className="text-xs text-blue-600 hover:text-blue-700"
          >
            Refresh
          </button>
        </div>

        {loadingJobs && (
          <p className="text-sm text-zinc-400">Loading…</p>
        )}

        {!loadingJobs && recentJobs.length === 0 && (
          <p className="text-sm text-zinc-400">No jobs yet.</p>
        )}

        {!loadingJobs && recentJobs.length > 0 && (
          <div className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white overflow-hidden">
            {recentJobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-zinc-800 capitalize">
                    {job.job_type.replace("_", " ")}
                  </p>
                  <p className="text-xs text-zinc-400">
                    {job.processed_rows.toLocaleString()} rows processed
                    {job.failed_rows > 0 && (
                      <span className="text-red-500"> · {job.failed_rows} failed</span>
                    )}
                  </p>
                </div>
                <JobStatusBadge status={job.status} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Icons ─────────────────────────────────────────────────────────────────────

function WriteIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
    </svg>
  );
}

function DeleteIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75" />
    </svg>
  );
}
