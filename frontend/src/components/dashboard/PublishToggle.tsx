"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";

interface PublishToggleProps {
  dashboardId: string;
  /** Initial published state from the server. */
  initialIsPublished: boolean;
  /** Called after the state changes successfully. */
  onChange?: (isPublished: boolean) => void;
}

export default function PublishToggle({
  dashboardId,
  initialIsPublished,
  onChange,
}: PublishToggleProps) {
  const [isPublished, setIsPublished] = useState(initialIsPublished);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleToggle() {
    setIsLoading(true);
    setError(null);
    const action = isPublished ? "unpublish" : "publish";
    try {
      const data = await fetchApi<{ id: string; is_published: boolean }>(
        `/api/dashboards/${dashboardId}/${action}`,
        { method: "POST" }
      );
      setIsPublished(data.is_published);
      onChange?.(data.is_published);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} dashboard`);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={handleToggle}
        disabled={isLoading}
        aria-pressed={isPublished}
        className={[
          "inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50",
          isPublished
            ? "bg-green-100 text-green-800 hover:bg-green-200 border border-green-300"
            : "bg-zinc-100 text-zinc-700 hover:bg-zinc-200 border border-zinc-300",
        ].join(" ")}
      >
        {/* Toggle indicator */}
        <span
          className={[
            "inline-block h-2 w-2 rounded-full",
            isPublished ? "bg-green-500" : "bg-zinc-400",
          ].join(" ")}
        />
        {isLoading ? "Updating..." : isPublished ? "Published" : "Unpublished"}
      </button>

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}
