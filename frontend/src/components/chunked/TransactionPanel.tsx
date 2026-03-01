"use client";

import { useCallback, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface BatchOperation {
  operation_type: string;
  target: string;
  payload: Record<string, unknown>;
}

interface TransactionalBatch {
  id: string;
  model_id: string;
  status: string;
  operations: BatchOperation[];
  created_at: string;
  committed_at: string | null;
  expires_at: string | null;
}

interface TransactionPanelProps {
  modelId: string;
  onCommit?: (batchId: string) => void;
  onRollback?: (batchId: string) => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiPost(path: string, body?: Record<string, unknown>) {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

async function apiGet(path: string) {
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
    open: "bg-blue-100 text-blue-800",
    committed: "bg-green-100 text-green-800",
    rolled_back: "bg-yellow-100 text-yellow-800",
    expired: "bg-gray-100 text-gray-800",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        colors[status] || "bg-gray-100 text-gray-800"
      }`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function TransactionPanel({
  modelId,
  onCommit,
  onRollback,
}: TransactionPanelProps) {
  const [batch, setBatch] = useState<TransactionalBatch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New operation form state
  const [opType, setOpType] = useState("write_cell");
  const [opTarget, setOpTarget] = useState("");
  const [opPayload, setOpPayload] = useState("{}");

  const createBatch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: TransactionalBatch = await apiPost(
        `/models/${modelId}/transactions`
      );
      setBatch(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create batch");
    } finally {
      setLoading(false);
    }
  }, [modelId]);

  const addOperation = useCallback(async () => {
    if (!batch) return;
    setError(null);
    try {
      const payload = JSON.parse(opPayload);
      const data: TransactionalBatch = await apiPost(
        `/transactions/${batch.id}/operations`,
        {
          operation_type: opType,
          target: opTarget,
          payload,
        }
      );
      setBatch(data);
      setOpTarget("");
      setOpPayload("{}");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to add operation"
      );
    }
  }, [batch, opType, opTarget, opPayload]);

  const commitBatch = useCallback(async () => {
    if (!batch) return;
    setLoading(true);
    setError(null);
    try {
      const data: TransactionalBatch = await apiPost(
        `/transactions/${batch.id}/commit`
      );
      setBatch(data);
      onCommit?.(batch.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to commit");
    } finally {
      setLoading(false);
    }
  }, [batch, onCommit]);

  const rollbackBatch = useCallback(async () => {
    if (!batch) return;
    setLoading(true);
    setError(null);
    try {
      const data: TransactionalBatch = await apiPost(
        `/transactions/${batch.id}/rollback`
      );
      setBatch(data);
      onRollback?.(batch.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rollback");
    } finally {
      setLoading(false);
    }
  }, [batch, onRollback]);

  const refreshBatch = useCallback(async () => {
    if (!batch) return;
    try {
      const data: TransactionalBatch = await apiGet(
        `/transactions/${batch.id}`
      );
      setBatch(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh");
    }
  }, [batch]);

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Transactional Batch
      </h3>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {!batch ? (
        <div className="flex flex-col items-center gap-3 py-8">
          <p className="text-sm text-gray-500">
            Create a transaction to group multiple operations into an atomic
            batch.
          </p>
          <button
            onClick={createBatch}
            disabled={loading}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Creating..." : "Start Transaction"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Batch header */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">
                Batch{" "}
                <span className="font-mono text-gray-700">
                  {batch.id.slice(0, 8)}...
                </span>
              </p>
              <p className="text-xs text-gray-400">
                Created {new Date(batch.created_at).toLocaleString()}
              </p>
            </div>
            {statusBadge(batch.status)}
          </div>

          {/* Operations list */}
          <div>
            <h4 className="mb-2 text-sm font-medium text-gray-700">
              Operations ({batch.operations?.length || 0})
            </h4>
            {batch.operations && batch.operations.length > 0 ? (
              <div className="max-h-48 divide-y overflow-auto rounded-md border">
                {batch.operations.map((op, idx) => (
                  <div key={idx} className="px-3 py-2 text-xs">
                    <span className="mr-2 font-medium text-blue-700">
                      {op.operation_type}
                    </span>
                    <span className="font-mono text-gray-500">
                      {op.target.length > 20
                        ? `${op.target.slice(0, 20)}...`
                        : op.target}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400">No operations yet.</p>
            )}
          </div>

          {/* Add operation form (only when open) */}
          {batch.status === "open" && (
            <div className="space-y-2 rounded-md border bg-gray-50 p-3">
              <h4 className="text-sm font-medium text-gray-700">
                Add Operation
              </h4>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-gray-500">Type</label>
                  <select
                    value={opType}
                    onChange={(e) => setOpType(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                  >
                    <option value="write_cell">Write Cell</option>
                    <option value="delete_cell">Delete Cell</option>
                    <option value="update_item">Update Item</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Target</label>
                  <input
                    type="text"
                    value={opTarget}
                    onChange={(e) => setOpTarget(e.target.value)}
                    placeholder="Target ID"
                    className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500">Payload (JSON)</label>
                <textarea
                  value={opPayload}
                  onChange={(e) => setOpPayload(e.target.value)}
                  rows={2}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 font-mono text-xs"
                />
              </div>
              <button
                onClick={addOperation}
                disabled={!opTarget}
                className="rounded bg-gray-200 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-300 disabled:opacity-50"
              >
                Add
              </button>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-2">
            {batch.status === "open" && (
              <>
                <button
                  onClick={commitBatch}
                  disabled={loading}
                  className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {loading ? "Committing..." : "Commit"}
                </button>
                <button
                  onClick={rollbackBatch}
                  disabled={loading}
                  className="rounded-md bg-red-100 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-200 disabled:opacity-50"
                >
                  Rollback
                </button>
              </>
            )}
            <button
              onClick={refreshBatch}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              Refresh
            </button>
            {batch.status !== "open" && (
              <button
                onClick={() => setBatch(null)}
                className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
              >
                New Transaction
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
