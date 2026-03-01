"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SSOLoginButtonProps {
  /** If provided, uses this workspace ID directly without showing the input. */
  workspaceId?: string;
  apiBase?: string;
  /** Called with the JWT access token after a successful SSO login. */
  onSuccess?: (accessToken: string, userEmail: string) => void;
  /** Called when SSO login fails. */
  onError?: (message: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCallbackCodeFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("code");
}

function getStateFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("state");
}

function getWorkspaceIdFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("workspace_id");
}

function storeToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("dynaplan_token", token);
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SSOLoginButton({
  workspaceId: propWorkspaceId,
  apiBase = "http://localhost:8000",
  onSuccess,
  onError,
}: SSOLoginButtonProps) {
  const [workspaceInput, setWorkspaceInput] = useState(propWorkspaceId ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callbackProcessed, setCallbackProcessed] = useState(false);

  // Handle SSO callback automatically on mount if ?code= is present in URL
  const processCallback = useCallback(
    async (code: string, state: string, wsId: string) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${apiBase}/sso/${wsId}/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, state }),
        });
        if (!resp.ok) {
          const errData = await resp.json().catch(() => ({}));
          throw new Error(errData.detail ?? `SSO callback failed: ${resp.statusText}`);
        }
        const data = await resp.json();
        storeToken(data.access_token);
        onSuccess?.(data.access_token, data.email);
        // Clean up the URL
        if (typeof window !== "undefined") {
          const cleanUrl = window.location.pathname;
          window.history.replaceState({}, "", cleanUrl);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "SSO login failed";
        setError(msg);
        onError?.(msg);
      } finally {
        setLoading(false);
      }
    },
    [apiBase, onSuccess, onError]
  );

  useEffect(() => {
    if (callbackProcessed) return;
    const code = getCallbackCodeFromUrl();
    const state = getStateFromUrl();
    const wsIdFromUrl = getWorkspaceIdFromUrl() ?? propWorkspaceId;
    if (code && state && wsIdFromUrl) {
      setCallbackProcessed(true);
      processCallback(code, state, wsIdFromUrl);
    }
  }, [callbackProcessed, propWorkspaceId, processCallback]);

  async function handleSSOLogin() {
    const wsId = propWorkspaceId ?? workspaceInput.trim();
    if (!wsId) {
      setError("Please enter a workspace ID.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/sso/${wsId}/login`);
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail ?? `No SSO provider found for workspace.`);
      }
      const data = await resp.json();
      // Redirect the browser to the identity provider's authorization URL
      if (typeof window !== "undefined") {
        window.location.href = data.redirect_url;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to initiate SSO login";
      setError(msg);
      onError?.(msg);
      setLoading(false);
    }
  }

  // While processing a callback, show a loading state
  if (loading && callbackProcessed) {
    return (
      <div className="flex flex-col items-center gap-3 p-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
        <p className="text-sm text-zinc-500">Completing SSO sign-in...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {!propWorkspaceId && (
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="sso-workspace-id"
            className="text-xs font-medium text-zinc-600"
          >
            Workspace ID
          </label>
          <input
            id="sso-workspace-id"
            type="text"
            value={workspaceInput}
            onChange={(e) => setWorkspaceInput(e.target.value)}
            placeholder="Enter your workspace ID"
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleSSOLogin}
        disabled={loading}
        className="flex items-center justify-center gap-2 rounded-md border border-zinc-300 bg-white px-4 py-2.5 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-50 transition-colors"
      >
        {loading ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-400 border-t-transparent" />
            Redirecting...
          </>
        ) : (
          <>
            {/* Shield icon for SSO */}
            <svg
              className="h-4 w-4 text-violet-600"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"
              />
            </svg>
            Sign in with SSO
          </>
        )}
      </button>
    </div>
  );
}
