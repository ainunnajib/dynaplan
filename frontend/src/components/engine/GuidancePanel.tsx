"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface GuidanceRule {
  id: string;
  profile_type: string;
  rule_code: string;
  severity: "info" | "warning" | "error";
  title: string;
  description: string;
  threshold_value: number | null;
  created_at: string;
}

interface RuleViolation {
  rule_code: string;
  severity: string;
  title: string;
  description: string;
  threshold_value: number | null;
  actual_value: number | null;
}

interface EvaluationResult {
  model_id: string;
  profile_type: string;
  violations: RuleViolation[];
  passed: boolean;
}

interface GuidancePanelProps {
  modelId: string;
  profileType?: "classic" | "polaris";
}

const severityColors: Record<string, string> = {
  info: "bg-blue-50 text-blue-700 border-blue-200",
  warning: "bg-yellow-50 text-yellow-700 border-yellow-200",
  error: "bg-red-50 text-red-700 border-red-200",
};

const severityBadge: Record<string, string> = {
  info: "bg-blue-100 text-blue-800",
  warning: "bg-yellow-100 text-yellow-800",
  error: "bg-red-100 text-red-800",
};

export function GuidancePanel({ modelId, profileType }: GuidancePanelProps) {
  const { token } = useAuth();
  const [rules, setRules] = useState<GuidanceRule[]>([]);
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRules = useCallback(async () => {
    if (!token) return;
    try {
      const url = profileType
        ? `${API_BASE}/engine-guidance/${profileType}`
        : `${API_BASE}/engine-guidance`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setRules((await res.json()) as GuidanceRule[]);
        setError(null);
      }
    } catch {
      setError("Failed to load guidance rules");
    } finally {
      setLoading(false);
    }
  }, [token, profileType]);

  useEffect(() => {
    void fetchRules();
  }, [fetchRules]);

  const handleEvaluate = async () => {
    if (!token) return;
    setEvaluating(true);
    try {
      const res = await fetch(
        `${API_BASE}/models/${modelId}/engine-profile/evaluate`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        setEvaluation((await res.json()) as EvaluationResult);
      } else if (res.status === 404) {
        setError("No engine profile configured. Set a profile first.");
      }
    } catch {
      setError("Failed to evaluate model");
    } finally {
      setEvaluating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-gray-500">Loading guidance rules...</div>
    );
  }

  return (
    <div className="space-y-6 rounded-lg border p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Design Guidance</h2>
        <button
          onClick={handleEvaluate}
          disabled={evaluating}
          className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {evaluating ? "Evaluating..." : "Evaluate Model"}
        </button>
      </div>

      {error && (
        <div className="rounded bg-red-50 p-3 text-sm text-red-600">{error}</div>
      )}

      {/* Evaluation results */}
      {evaluation && (
        <div
          className={`rounded border p-4 ${
            evaluation.passed
              ? "border-green-200 bg-green-50"
              : "border-red-200 bg-red-50"
          }`}
        >
          <div className="mb-2 font-medium">
            {evaluation.passed
              ? "All checks passed"
              : `${evaluation.violations.length} violation(s) found`}
          </div>
          {evaluation.violations.map((v, i) => (
            <div
              key={i}
              className={`mb-2 rounded border p-3 ${
                severityColors[v.severity] ?? ""
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    severityBadge[v.severity] ?? ""
                  }`}
                >
                  {v.severity.toUpperCase()}
                </span>
                <span className="font-medium">{v.title}</span>
              </div>
              <div className="mt-1 text-sm">{v.description}</div>
              {v.threshold_value != null && v.actual_value != null && (
                <div className="mt-1 text-xs">
                  Threshold: {v.threshold_value.toLocaleString()} | Actual:{" "}
                  {v.actual_value.toLocaleString()}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Rules list */}
      <div>
        <h3 className="mb-3 text-sm font-medium text-gray-600">
          Guidance Rules ({rules.length})
        </h3>
        {rules.length === 0 && (
          <div className="text-sm text-gray-400">
            No guidance rules configured.
          </div>
        )}
        <div className="space-y-2">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`rounded border p-3 ${
                severityColors[rule.severity] ?? ""
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-medium ${
                    severityBadge[rule.severity] ?? ""
                  }`}
                >
                  {rule.severity.toUpperCase()}
                </span>
                <span className="font-medium">{rule.title}</span>
                <span className="ml-auto text-xs text-gray-400">
                  {rule.rule_code}
                </span>
              </div>
              <div className="mt-1 text-sm">{rule.description}</div>
              {rule.threshold_value != null && (
                <div className="mt-1 text-xs text-gray-500">
                  Threshold: {rule.threshold_value.toLocaleString()}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
