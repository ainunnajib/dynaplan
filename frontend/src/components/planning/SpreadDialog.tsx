"use client";

import { useState, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

type SpreadMethod = "even" | "proportional" | "weighted";

interface MemberValue {
  member_id: string;
  value: number;
}

interface SpreadResponse {
  line_item_id: string;
  cells_updated: MemberValue[];
}

interface ChildMember {
  id: string;
  name: string;
  currentValue?: number;
}

interface SpreadDialogProps {
  lineItemId: string;
  parentMemberId: string;
  parentMemberName: string;
  children: ChildMember[];
  onSpread?: (updatedCells: MemberValue[]) => void;
  /** Optional trigger button label */
  triggerLabel?: string;
}

const METHOD_LABELS: Record<SpreadMethod, string> = {
  even: "Even",
  proportional: "Proportional",
  weighted: "Weighted",
};

const METHOD_DESCRIPTIONS: Record<SpreadMethod, string> = {
  even: "Distribute equally across all members",
  proportional: "Distribute based on existing values",
  weighted: "Distribute based on custom weights",
};

export default function SpreadDialog({
  lineItemId,
  parentMemberId,
  parentMemberName,
  children,
  onSpread,
  triggerLabel = "Spread",
}: SpreadDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [targetValue, setTargetValue] = useState("");
  const [method, setMethod] = useState<SpreadMethod>("even");
  const [weights, setWeights] = useState<string[]>(
    children.map(() => "1")
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<MemberValue[] | null>(null);

  function openDialog() {
    setIsOpen(true);
    setTargetValue("");
    setMethod("even");
    setWeights(children.map(() => "1"));
    setError(null);
    setPreview(null);
  }

  function closeDialog() {
    if (isSubmitting) return;
    setIsOpen(false);
  }

  function computePreview(): MemberValue[] | null {
    const total = parseFloat(targetValue);
    if (isNaN(total) || children.length === 0) return null;

    const count = children.length;

    if (method === "even") {
      const share = total / count;
      return children.map((c) => ({ member_id: c.id, value: share }));
    }

    if (method === "proportional") {
      const existing = children.map((c) => c.currentValue ?? 0);
      const sum = existing.reduce((a, b) => a + Math.abs(b), 0);
      if (sum === 0) {
        const share = total / count;
        return children.map((c) => ({ member_id: c.id, value: share }));
      }
      return children.map((c, i) => ({
        member_id: c.id,
        value: total * (Math.abs(existing[i]) / sum),
      }));
    }

    if (method === "weighted") {
      const parsedWeights = weights.map((w) => parseFloat(w) || 0);
      const weightSum = parsedWeights.reduce((a, b) => a + b, 0);
      if (weightSum === 0) {
        const share = total / count;
        return children.map((c) => ({ member_id: c.id, value: share }));
      }
      return children.map((c, i) => ({
        member_id: c.id,
        value: total * (parsedWeights[i] / weightSum),
      }));
    }

    return null;
  }

  function handleMethodChange(newMethod: SpreadMethod) {
    setMethod(newMethod);
    setPreview(null);
  }

  function handleTargetValueChange(val: string) {
    setTargetValue(val);
    setPreview(null);
  }

  function handlePreview() {
    const p = computePreview();
    setPreview(p);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const total = parseFloat(targetValue);
    if (isNaN(total)) {
      setError("Target value must be a valid number");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const body: Record<string, unknown> = {
        line_item_id: lineItemId,
        parent_member_id: parentMemberId,
        target_value: total,
        method,
      };

      if (method === "weighted") {
        body.weights = weights.map((w) => parseFloat(w) || 0);
      }

      const result = await fetchApi<SpreadResponse>("/planning/spread", {
        method: "POST",
        body: JSON.stringify(body),
      });

      onSpread?.(result.cells_updated);
      setIsOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to spread value");
    } finally {
      setIsSubmitting(false);
    }
  }

  const previewData = preview ?? computePreview();
  const totalValue = parseFloat(targetValue);
  const isValidTotal = !isNaN(totalValue);

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
      >
        {triggerLabel}
      </button>

      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDialog();
          }}
        >
          <div className="w-full max-w-lg rounded-xl bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
              <div>
                <h2 className="text-base font-semibold text-zinc-900">
                  Spread Value
                </h2>
                <p className="text-xs text-zinc-500 mt-0.5">
                  Distributing from: {parentMemberName}
                </p>
              </div>
              <button
                type="button"
                onClick={closeDialog}
                disabled={isSubmitting}
                className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors disabled:opacity-50"
                aria-label="Close"
              >
                <CloseIcon className="h-5 w-5" />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
              {/* Target value */}
              <div>
                <label
                  htmlFor="target-value"
                  className="block text-sm font-medium text-zinc-700"
                >
                  Target value <span className="text-red-500">*</span>
                </label>
                <input
                  id="target-value"
                  type="number"
                  step="any"
                  value={targetValue}
                  onChange={(e) => handleTargetValueChange(e.target.value)}
                  placeholder="e.g. 1000000"
                  className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                  disabled={isSubmitting}
                />
              </div>

              {/* Method selector */}
              <div>
                <label className="block text-sm font-medium text-zinc-700">
                  Spread method
                </label>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {(Object.keys(METHOD_LABELS) as SpreadMethod[]).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => handleMethodChange(m)}
                      disabled={isSubmitting}
                      className={`rounded-md border px-3 py-2 text-xs font-medium transition-colors text-left ${
                        method === m
                          ? "border-blue-500 bg-blue-50 text-blue-700"
                          : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50"
                      } disabled:opacity-50`}
                    >
                      <div className="font-semibold">{METHOD_LABELS[m]}</div>
                      <div className="text-zinc-500 mt-0.5 font-normal">
                        {METHOD_DESCRIPTIONS[m]}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Weighted inputs */}
              {method === "weighted" && children.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-zinc-700">
                    Weights
                  </label>
                  <div className="mt-2 space-y-2">
                    {children.map((child, i) => (
                      <div key={child.id} className="flex items-center gap-2">
                        <span className="w-32 truncate text-sm text-zinc-600">
                          {child.name}
                        </span>
                        <input
                          type="number"
                          step="any"
                          min="0"
                          value={weights[i]}
                          onChange={(e) => {
                            const newWeights = [...weights];
                            newWeights[i] = e.target.value;
                            setWeights(newWeights);
                            setPreview(null);
                          }}
                          className="w-24 rounded-md border border-zinc-300 px-2 py-1 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                          disabled={isSubmitting}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Preview */}
              {isValidTotal && children.length > 0 && (
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-zinc-700">
                      Distribution preview
                    </span>
                    <button
                      type="button"
                      onClick={handlePreview}
                      className="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Refresh
                    </button>
                  </div>
                  <div className="mt-2 rounded-md border border-zinc-200 overflow-hidden">
                    {previewData ? (
                      <table className="w-full text-sm">
                        <thead className="bg-zinc-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-zinc-500">
                              Member
                            </th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-zinc-500">
                              Value
                            </th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-zinc-500">
                              Share
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-zinc-100">
                          {previewData.map((item) => {
                            const child = children.find(
                              (c) => c.id === item.member_id
                            );
                            const share =
                              totalValue !== 0
                                ? ((item.value / Math.abs(totalValue)) * 100).toFixed(1)
                                : "0.0";
                            return (
                              <tr key={item.member_id}>
                                <td className="px-3 py-1.5 text-zinc-700">
                                  {child?.name ?? item.member_id}
                                </td>
                                <td className="px-3 py-1.5 text-right font-mono text-zinc-900">
                                  {item.value.toLocaleString(undefined, {
                                    maximumFractionDigits: 2,
                                  })}
                                </td>
                                <td className="px-3 py-1.5 text-right text-zinc-500">
                                  {share}%
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                        <tfoot className="bg-zinc-50 border-t border-zinc-200">
                          <tr>
                            <td className="px-3 py-1.5 text-xs font-semibold text-zinc-600">
                              Total
                            </td>
                            <td className="px-3 py-1.5 text-right font-mono text-xs font-semibold text-zinc-900">
                              {previewData
                                .reduce((s, i) => s + i.value, 0)
                                .toLocaleString(undefined, {
                                  maximumFractionDigits: 2,
                                })}
                            </td>
                            <td className="px-3 py-1.5 text-right text-xs text-zinc-500">
                              100%
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    ) : (
                      <p className="px-3 py-2 text-sm text-zinc-400">
                        Enter a target value to see the distribution.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {error && (
                <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
                  {error}
                </p>
              )}

              {/* Footer */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeDialog}
                  disabled={isSubmitting}
                  className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !isValidTotal || children.length === 0}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {isSubmitting ? "Applying..." : "Apply Spread"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
