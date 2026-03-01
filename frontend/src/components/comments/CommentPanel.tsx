"use client";

import { useCallback, useEffect, useState } from "react";
import CommentInput from "./CommentInput";

export interface Comment {
  id: string;
  model_id: string;
  target_type: "module" | "line_item" | "cell";
  target_id: string;
  content: string;
  author_id: string;
  author_email: string | null;
  author_name: string | null;
  parent_id: string | null;
  is_resolved: boolean;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  mention_user_ids: string[];
}

interface Props {
  modelId: string;
  targetType: "module" | "line_item" | "cell";
  targetId: string;
  apiBase?: string;
  authToken?: string;
  onClose?: () => void;
}

type CommentTree = Comment & { replies: Comment[] };

function buildTree(comments: Comment[]): CommentTree[] {
  const roots: CommentTree[] = [];
  const map: Record<string, CommentTree> = {};
  for (const c of comments) {
    map[c.id] = { ...c, replies: [] };
  }
  for (const c of comments) {
    if (c.parent_id && map[c.parent_id]) {
      map[c.parent_id].replies.push(map[c.id]);
    } else if (!c.parent_id) {
      roots.push(map[c.id]);
    }
  }
  return roots;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

interface CommentItemProps {
  comment: CommentTree;
  depth?: number;
  modelId: string;
  authToken?: string;
  apiBase: string;
  onRefresh: () => void;
}

function CommentItem({ comment, depth = 0, modelId, authToken, apiBase, onRefresh }: CommentItemProps) {
  const [showReply, setShowReply] = useState(false);
  const [isResolving, setIsResolving] = useState(false);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };

  async function handleResolveToggle() {
    setIsResolving(true);
    const endpoint = comment.is_resolved
      ? `${apiBase}/comments/${comment.id}/unresolve`
      : `${apiBase}/comments/${comment.id}/resolve`;
    try {
      await fetch(endpoint, { method: "POST", headers });
      onRefresh();
    } finally {
      setIsResolving(false);
    }
  }

  async function handleReply(content: string) {
    await fetch(`${apiBase}/models/${modelId}/comments`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model_id: modelId,
        target_type: comment.target_type,
        target_id: comment.target_id,
        content,
        parent_id: comment.id,
      }),
    });
    setShowReply(false);
    onRefresh();
  }

  async function handleDelete() {
    if (!window.confirm("Delete this comment?")) return;
    await fetch(`${apiBase}/comments/${comment.id}`, {
      method: "DELETE",
      headers,
    });
    onRefresh();
  }

  const indentClass = depth > 0 ? "ml-6 border-l-2 border-zinc-100 pl-3" : "";

  return (
    <div className={`${indentClass} py-2`}>
      <div className={`rounded-lg border px-3 py-2 ${comment.is_resolved ? "bg-zinc-50 opacity-70" : "bg-white"}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <div className="h-6 w-6 rounded-full bg-violet-100 flex items-center justify-center shrink-0">
              <span className="text-xs font-semibold text-violet-700">
                {(comment.author_email ?? "?")[0].toUpperCase()}
              </span>
            </div>
            <span className="text-xs font-medium text-zinc-900 truncate">
              {comment.author_name ?? comment.author_email ?? "Unknown"}
            </span>
            <span className="text-xs text-zinc-400 shrink-0">
              {formatRelativeTime(comment.created_at)}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {comment.is_resolved && (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                Resolved
              </span>
            )}
            <button
              type="button"
              onClick={handleResolveToggle}
              disabled={isResolving}
              title={comment.is_resolved ? "Unresolve" : "Resolve"}
              className="rounded p-1 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 transition-colors"
            >
              <CheckCircleIcon className={`h-3.5 w-3.5 ${comment.is_resolved ? "text-green-600" : ""}`} />
            </button>
            <button
              type="button"
              onClick={handleDelete}
              title="Delete comment"
              className="rounded p-1 text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
            >
              <TrashIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <p className="mt-1.5 text-sm text-zinc-700 whitespace-pre-wrap break-words">
          {comment.content}
        </p>

        {depth === 0 && (
          <button
            type="button"
            onClick={() => setShowReply((v) => !v)}
            className="mt-1 text-xs text-violet-600 hover:text-violet-800 transition-colors"
          >
            {showReply ? "Cancel reply" : "Reply"}
          </button>
        )}
      </div>

      {showReply && (
        <div className="ml-6 mt-1">
          <CommentInput
            onSubmit={handleReply}
            onCancel={() => setShowReply(false)}
            placeholder="Write a reply..."
            submitLabel="Reply"
          />
        </div>
      )}

      {comment.replies.map((reply) => (
        <CommentItem
          key={reply.id}
          comment={{ ...reply, replies: [] }}
          depth={depth + 1}
          modelId={modelId}
          authToken={authToken}
          apiBase={apiBase}
          onRefresh={onRefresh}
        />
      ))}
    </div>
  );
}

export default function CommentPanel({
  modelId,
  targetType,
  targetId,
  apiBase = "http://localhost:8000",
  authToken,
  onClose,
}: Props) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };

  const fetchComments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const url = `${apiBase}/models/${modelId}/comments?target_type=${targetType}&target_id=${encodeURIComponent(targetId)}`;
      const res = await fetch(url, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Comment[] = await res.json();
      setComments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load comments");
    } finally {
      setIsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId, targetType, targetId, apiBase, authToken]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  async function handleNewComment(content: string) {
    const res = await fetch(`${apiBase}/models/${modelId}/comments`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model_id: modelId,
        target_type: targetType,
        target_id: targetId,
        content,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? "Failed to post comment");
    }
    await fetchComments();
  }

  const tree = buildTree(comments);
  const unresolvedCount = comments.filter((c) => !c.is_resolved && !c.parent_id).length;

  return (
    <div className="flex h-full flex-col bg-white border-l border-zinc-200 w-80 shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <ChatBubbleIcon className="h-4 w-4 text-zinc-500" />
          <h2 className="text-sm font-semibold text-zinc-900">
            Comments
            {unresolvedCount > 0 && (
              <span className="ml-1.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-xs font-medium text-violet-700">
                {unresolvedCount}
              </span>
            )}
          </h2>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 transition-colors"
          >
            <XIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Comment list */}
      <div className="flex-1 overflow-y-auto px-3">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <span className="text-sm text-zinc-400">Loading comments...</span>
          </div>
        ) : error ? (
          <div className="py-4 text-center">
            <p className="text-sm text-red-600">{error}</p>
            <button
              type="button"
              onClick={fetchComments}
              className="mt-2 text-xs text-violet-600 hover:underline"
            >
              Retry
            </button>
          </div>
        ) : tree.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <ChatBubbleIcon className="h-8 w-8 text-zinc-300 mb-2" />
            <p className="text-sm text-zinc-500">No comments yet</p>
            <p className="text-xs text-zinc-400 mt-1">Be the first to comment on this item.</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {tree.map((comment) => (
              <CommentItem
                key={comment.id}
                comment={comment}
                modelId={modelId}
                authToken={authToken}
                apiBase={apiBase}
                onRefresh={fetchComments}
              />
            ))}
          </div>
        )}
      </div>

      {/* New comment input */}
      <div className="border-t border-zinc-200 px-3 py-3">
        <CommentInput
          onSubmit={handleNewComment}
          placeholder={`Comment on this ${targetType.replace("_", " ")}...`}
        />
      </div>
    </div>
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

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}
