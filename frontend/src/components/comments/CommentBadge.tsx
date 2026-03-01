"use client";

import { useCallback, useEffect, useState } from "react";
import CommentPanel from "./CommentPanel";

interface Props {
  modelId: string;
  targetType: "module" | "line_item" | "cell";
  targetId: string;
  apiBase?: string;
  authToken?: string;
}

export default function CommentBadge({
  modelId,
  targetType,
  targetId,
  apiBase = "http://localhost:8000",
  authToken,
}: Props) {
  const [count, setCount] = useState<number | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const fetchCount = useCallback(async () => {
    try {
      const headers: Record<string, string> = authToken
        ? { Authorization: `Bearer ${authToken}` }
        : {};
      const url = `${apiBase}/models/${modelId}/comments?target_type=${targetType}&target_id=${encodeURIComponent(targetId)}`;
      const res = await fetch(url, { headers });
      if (!res.ok) return;
      const data: unknown[] = await res.json();
      setCount(data.length);
    } catch {
      // silently ignore fetch errors for the badge
    }
  }, [modelId, targetType, targetId, apiBase, authToken]);

  useEffect(() => {
    fetchCount();
  }, [fetchCount]);

  if (count === null) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setIsPanelOpen(true)}
        title={`${count} comment${count !== 1 ? "s" : ""}`}
        className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-white px-1.5 py-0.5 text-xs text-zinc-500 hover:border-violet-300 hover:text-violet-700 hover:bg-violet-50 transition-colors"
      >
        <ChatBubbleIcon className="h-3 w-3" />
        {count > 0 && (
          <span className="font-medium">{count > 99 ? "99+" : count}</span>
        )}
      </button>

      {isPanelOpen && (
        <div className="fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="flex-1 bg-black/20"
            onClick={() => {
              setIsPanelOpen(false);
              fetchCount();
            }}
          />
          {/* Panel slides in from right */}
          <CommentPanel
            modelId={modelId}
            targetType={targetType}
            targetId={targetId}
            apiBase={apiBase}
            authToken={authToken}
            onClose={() => {
              setIsPanelOpen(false);
              fetchCount();
            }}
          />
        </div>
      )}
    </>
  );
}

function ChatBubbleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 0 1 .865-.501 48.172 48.172 0 0 0 3.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0 0 12 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018Z"
      />
    </svg>
  );
}
