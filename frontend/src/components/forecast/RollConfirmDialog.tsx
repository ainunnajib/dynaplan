"use client";

import { useState, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

interface RollResult {
  periods_rolled: number;
  cells_archived: number;
  new_switchover_period: string | null;
}

interface RollConfirmDialogProps {
  modelId: string;
  nextPeriod: string | null;
  /** Called with the roll result after a successful roll. */
  onConfirm: (result: RollResult) => void;
  /** Called when the user cancels. */
  onCancel: () => void;
}

export default function RollConfirmDialog({
  modelId,
  nextPeriod,
  onConfirm,
  onCancel,
}: RollConfirmDialogProps) {
  const [periodsToRoll, setPeriodsToRoll] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm(e: FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await fetchApi<RollResult>(
        `/api/models/${modelId}/forecast/roll?periods_to_roll=${periodsToRoll}`,
        { method: "POST" }
      );
      onConfirm(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to roll forecast."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onCancel();
      }}
    >
      <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4">
          <h2 className="text-base font-semibold text-zinc-900">
            Roll Forecast Forward
          </h2>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleConfirm} className="px-6 py-5 space-y-4">
          {/* What will happen */}
          <div className="rounded-md bg-blue-50 px-4 py-3 text-sm text-blue-800 space-y-1">
            <p className="font-medium">What will happen:</p>
            <ul className="list-disc list-inside space-y-0.5 text-blue-700">
              <li>
                Forecast cell values for the oldest{" "}
                {periodsToRoll === 1 ? "period" : `${periodsToRoll} periods`} will be
                copied into the actuals version.
              </li>
              <li>
                The forecast switchover period will advance by{" "}
                {periodsToRoll === 1 ? "1 month" : `${periodsToRoll} months`}.
              </li>
              {nextPeriod && (
                <li>
                  New switchover will be set to approximately{" "}
                  <strong>{nextPeriod}</strong> (+ additional periods if more than 1).
                </li>
              )}
            </ul>
          </div>

          {/* Periods to roll */}
          <div>
            <label
              htmlFor="periods-to-roll"
              className="block text-sm font-medium text-zinc-700"
            >
              Periods to Roll
            </label>
            <input
              id="periods-to-roll"
              type="number"
              min={1}
              max={120}
              value={periodsToRoll}
              onChange={(e) =>
                setPeriodsToRoll(Math.max(1, Number(e.target.value)))
              }
              disabled={isSubmitting}
              className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            />
            <p className="mt-1 text-xs text-zinc-400">
              Number of months to advance the forecast switchover.
            </p>
          </div>

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
              {error}
            </p>
          )}

          {/* Footer buttons */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || periodsToRoll < 1}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting
                ? "Rolling..."
                : `Roll ${periodsToRoll === 1 ? "1 Period" : `${periodsToRoll} Periods`} Forward`}
            </button>
          </div>
        </form>
      </div>
    </div>
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
