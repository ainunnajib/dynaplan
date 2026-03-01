"use client";

import { useState } from "react";
import JobProgress from "./JobProgress";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface CellInput {
  line_item_id: string;
  dimension_members: string[];
  value: unknown;
}

interface BulkWriteFormProps {
  modelId: string;
  onSuccess?: (jobId: string) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseCells(raw: string): CellInput[] | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed as CellInput[];
  } catch {
    return null;
  }
}

const CHUNK_SIZE_OPTIONS = [10, 50, 100, 250, 500];

const EXAMPLE_JSON = JSON.stringify(
  [
    { line_item_id: "<uuid>", dimension_members: ["<dim-uuid>"], value: 42 },
    { line_item_id: "<uuid>", dimension_members: ["<dim-uuid>"], value: "hello" },
  ],
  null,
  2
);

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * BulkWriteForm — accepts JSON cell data, parses it, and submits a bulk write job.
 *
 * Shows a preview of parsed row count, chunk size selector, and tracks the
 * resulting job via the JobProgress component.
 */
export default function BulkWriteForm({ modelId, onSuccess }: BulkWriteFormProps) {
  const [rawJson, setRawJson] = useState("");
  const [chunkSize, setChunkSize] = useState(100);
  const [parsedCount, setParsedCount] = useState<number | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleJsonChange(value: string) {
    setRawJson(value);
    setSubmitError(null);

    if (!value.trim()) {
      setParsedCount(null);
      setParseError(null);
      return;
    }

    const cells = parseCells(value);
    if (cells === null) {
      setParseError("Invalid JSON. Expected an array of cell objects.");
      setParsedCount(null);
    } else {
      setParseError(null);
      setParsedCount(cells.length);
    }
  }

  async function handleSubmit() {
    const cells = parseCells(rawJson);
    if (!cells) return;

    setSubmitting(true);
    setSubmitError(null);

    const token = getAuthToken();
    try {
      const resp = await fetch(`${API_BASE_URL}/models/${modelId}/bulk/write`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ cells, chunk_size: chunkSize }),
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(
          (body as { detail?: string }).detail ?? `Write failed: ${resp.status}`
        );
      }

      const job = await resp.json();
      setJobId(job.id as string);
      onSuccess?.(job.id as string);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Bulk write failed");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    !submitting && parsedCount !== null && parsedCount > 0 && !parseError;

  return (
    <div className="space-y-4">
      {/* JSON input */}
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">
          Cell data (JSON array)
        </label>
        <textarea
          value={rawJson}
          onChange={(e) => handleJsonChange(e.target.value)}
          rows={10}
          placeholder={EXAMPLE_JSON}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-xs text-zinc-800 shadow-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none resize-y"
        />
        {parseError && (
          <p className="mt-1 text-xs text-red-600">{parseError}</p>
        )}
        {parsedCount !== null && !parseError && (
          <p className="mt-1 text-xs text-zinc-500">
            {parsedCount.toLocaleString()} row{parsedCount !== 1 ? "s" : ""} parsed
          </p>
        )}
      </div>

      {/* Chunk size */}
      <div>
        <label className="block text-sm font-medium text-zinc-700 mb-1">
          Chunk size
        </label>
        <select
          value={chunkSize}
          onChange={(e) => setChunkSize(Number(e.target.value))}
          className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-700 focus:border-blue-400 focus:ring-1 focus:ring-blue-400 outline-none"
        >
          {CHUNK_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size} rows/chunk
            </option>
          ))}
        </select>
      </div>

      {/* Submit error */}
      {submitError && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
          {submitError}
        </p>
      )}

      {/* Submit button */}
      {!jobId && (
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? "Submitting…" : "Start bulk write"}
        </button>
      )}

      {/* Job progress */}
      {jobId && (
        <div className="mt-4">
          <p className="text-xs font-medium text-zinc-500 mb-2 uppercase tracking-wide">
            Job progress
          </p>
          <JobProgress
            jobId={jobId}
            onFinished={(data) => {
              if (data.status === "completed") {
                // Allow re-submission after completion
              }
            }}
          />
        </div>
      )}
    </div>
  );
}
