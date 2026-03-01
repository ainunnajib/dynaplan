"use client";

import { useCallback, useRef, useState } from "react";

const MAX_CHARS = 2000;

interface Props {
  onSubmit: (content: string) => Promise<void>;
  onCancel?: () => void;
  placeholder?: string;
  submitLabel?: string;
}

export default function CommentInput({
  onSubmit,
  onCancel,
  placeholder = "Write a comment... Use @email to mention someone.",
  submitLabel = "Comment",
}: Props) {
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const charCount = content.length;
  const isOverLimit = charCount > MAX_CHARS;
  const isEmpty = content.trim().length === 0;

  const handleSubmit = useCallback(async () => {
    if (isEmpty || isOverLimit || isSubmitting) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmit(content.trim());
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post comment");
    } finally {
      setIsSubmitting(false);
    }
  }, [content, isEmpty, isOverLimit, isSubmitting, onSubmit]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => {
            setContent(e.target.value);
            setError(null);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={3}
          className={[
            "w-full resize-none rounded-md border px-3 py-2 text-sm text-zinc-900",
            "placeholder-zinc-400 focus:outline-none focus:ring-2",
            isOverLimit
              ? "border-red-400 focus:border-red-500 focus:ring-red-200"
              : "border-zinc-300 focus:border-violet-500 focus:ring-violet-200",
          ].join(" ")}
          disabled={isSubmitting}
        />
        <span
          className={[
            "absolute bottom-2 right-2 text-xs select-none",
            isOverLimit ? "text-red-500 font-medium" : "text-zinc-400",
          ].join(" ")}
        >
          {charCount}/{MAX_CHARS}
        </span>
      </div>

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-400">
          Tip: Cmd+Enter to submit. Use @email@domain to mention someone.
        </span>
        <div className="flex items-center gap-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
              className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isEmpty || isOverLimit || isSubmitting}
            className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {isSubmitting ? "Posting..." : submitLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
