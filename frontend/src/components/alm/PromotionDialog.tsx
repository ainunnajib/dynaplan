"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("dynaplan_token");
}

// -- Types -------------------------------------------------------------------

interface ALMEnvironment {
  id: string;
  model_id: string;
  env_type: "dev" | "test" | "prod";
  name: string;
  description: string | null;
  source_env_id: string | null;
  is_locked: boolean;
}

interface RevisionTag {
  id: string;
  environment_id: string;
  tag_name: string;
  description: string | null;
}

interface PromotionRecord {
  id: string;
  source_env_id: string;
  target_env_id: string;
  revision_tag_id: string;
  promoted_by: string;
  status: "pending" | "in_progress" | "completed" | "failed" | "rolled_back";
  change_summary: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface PromotionDialogProps {
  /** Source environment to promote from. */
  sourceEnv: ALMEnvironment;
  /** All available environments (to pick the target). */
  environments: ALMEnvironment[];
  /** Available revision tags in the source environment. */
  tags: RevisionTag[];
  /** Called when the dialog closes (with or without promotion). */
  onClose: () => void;
  /** Called after a successful promotion initiation. */
  onPromotionCreated?: (record: PromotionRecord) => void;
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  in_progress: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  rolled_back: "bg-gray-100 text-gray-800",
};

// -- Component ---------------------------------------------------------------

export default function PromotionDialog({
  sourceEnv,
  environments,
  tags,
  onClose,
  onPromotionCreated,
}: PromotionDialogProps) {
  const [targetEnvId, setTargetEnvId] = useState("");
  const [tagId, setTagId] = useState("");
  const [promoting, setPromoting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Promotion history
  const [promotions, setPromotions] = useState<PromotionRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const targetOptions = environments.filter((e) => e.id !== sourceEnv.id);

  const fetchPromotions = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/environments/${sourceEnv.id}/promotions`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (resp.ok) {
        const data: PromotionRecord[] = await resp.json();
        setPromotions(data);
      }
    } catch {
      // Silently fail for history
    } finally {
      setLoadingHistory(false);
    }
  }, [sourceEnv.id]);

  useEffect(() => {
    fetchPromotions();
  }, [fetchPromotions]);

  const handlePromote = async () => {
    if (!targetEnvId || !tagId) return;
    setPromoting(true);
    setError(null);
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/environments/${sourceEnv.id}/promote`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            target_env_id: targetEnvId,
            revision_tag_id: tagId,
          }),
        }
      );
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || "Promotion failed");
      }
      const record: PromotionRecord = await resp.json();
      onPromotionCreated?.(record);
      await fetchPromotions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setPromoting(false);
    }
  };

  const handleCompleteOrFail = async (
    promotionId: string,
    action: "complete" | "fail"
  ) => {
    try {
      const token = getAuthToken();
      const resp = await fetch(
        `${API_BASE_URL}/promotions/${promotionId}/${action}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to ${action} promotion`);
      }
      await fetchPromotions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Promote from {sourceEnv.name}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Promotion form */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Target Environment
              </label>
              <select
                value={targetEnvId}
                onChange={(e) => setTargetEnvId(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Select target...</option>
                {targetOptions.map((env) => (
                  <option key={env.id} value={env.id}>
                    {env.name} ({env.env_type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Revision Tag
              </label>
              <select
                value={tagId}
                onChange={(e) => setTagId(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="">Select tag...</option>
                {tags.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.tag_name}
                    {tag.description ? ` - ${tag.description}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handlePromote}
              disabled={promoting || !targetEnvId || !tagId}
              className="w-full rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {promoting ? "Promoting..." : "Start Promotion"}
            </button>
          </div>

          {/* Promotion history */}
          <div>
            <h3 className="mb-2 text-sm font-medium text-gray-700">
              Promotion History
            </h3>
            {loadingHistory ? (
              <p className="text-xs text-gray-500">Loading...</p>
            ) : promotions.length === 0 ? (
              <p className="text-xs text-gray-500">
                No promotions yet from this environment.
              </p>
            ) : (
              <ul className="max-h-48 divide-y divide-gray-100 overflow-y-auto rounded-lg border border-gray-200">
                {promotions.map((promo) => (
                  <li
                    key={promo.id}
                    className="flex items-center justify-between px-3 py-2"
                  >
                    <div>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[promo.status] || "bg-gray-100 text-gray-800"}`}
                      >
                        {promo.status}
                      </span>
                      <span className="ml-2 text-xs text-gray-500">
                        {new Date(promo.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {(promo.status === "pending" ||
                      promo.status === "in_progress") && (
                      <div className="flex gap-1">
                        <button
                          onClick={() =>
                            handleCompleteOrFail(promo.id, "complete")
                          }
                          className="rounded bg-green-50 px-2 py-0.5 text-xs text-green-700 hover:bg-green-100"
                        >
                          Complete
                        </button>
                        <button
                          onClick={() =>
                            handleCompleteOrFail(promo.id, "fail")
                          }
                          className="rounded bg-red-50 px-2 py-0.5 text-xs text-red-700 hover:bg-red-100"
                        >
                          Fail
                        </button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t px-6 py-3">
          <button
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
