"use client";

import { useState, type FormEvent } from "react";
import { fetchApi } from "@/lib/api";

type Permission = "view" | "edit";

interface ShareDialogProps {
  dashboardId: string;
  /** Called after a share is successfully created. */
  onShared?: () => void;
}

export default function ShareDialog({ dashboardId, onShared }: ShareDialogProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [permission, setPermission] = useState<Permission>("view");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  function openDialog() {
    setIsOpen(true);
    setEmail("");
    setPermission("view");
    setError(null);
    setSuccessMessage(null);
  }

  function closeDialog() {
    if (isSubmitting) return;
    setIsOpen(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Email address is required");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await fetchApi(`/api/dashboards/${dashboardId}/share`, {
        method: "POST",
        body: JSON.stringify({ user_email: trimmedEmail, permission }),
      });
      setSuccessMessage(`Dashboard shared with ${trimmedEmail}`);
      setEmail("");
      onShared?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to share dashboard");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="rounded-md border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
      >
        Share
      </button>

      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDialog();
          }}
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-4 sm:px-6">
              <h2 className="text-base font-semibold text-zinc-900">Share Dashboard</h2>
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
            <form onSubmit={handleSubmit} className="space-y-4 px-4 py-5 sm:px-6">
              <div>
                <label
                  htmlFor="share-email"
                  className="block text-sm font-medium text-zinc-700"
                >
                  Email address <span className="text-red-500">*</span>
                </label>
                <input
                  id="share-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="colleague@example.com"
                  className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 placeholder-zinc-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  autoFocus
                  disabled={isSubmitting}
                />
              </div>

              <div>
                <label
                  htmlFor="share-permission"
                  className="block text-sm font-medium text-zinc-700"
                >
                  Permission
                </label>
                <select
                  id="share-permission"
                  value={permission}
                  onChange={(e) => setPermission(e.target.value as Permission)}
                  disabled={isSubmitting}
                  className="mt-1.5 block w-full rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="view">View only</option>
                  <option value="edit">Can edit</option>
                </select>
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

              {/* Footer */}
              <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:items-center sm:justify-end sm:gap-3">
                <button
                  type="button"
                  onClick={closeDialog}
                  disabled={isSubmitting}
                  className="w-full rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 sm:w-auto"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || !email.trim()}
                  className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50 sm:w-auto"
                >
                  {isSubmitting ? "Sharing..." : "Share"}
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
