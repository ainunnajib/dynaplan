"use client";

import { useState } from "react";

interface ApprovalDialogProps {
  taskName: string;
  action: "approve" | "reject";
  open: boolean;
  onClose: () => void;
  onConfirm: (comment: string) => void;
}

export function ApprovalDialog({
  taskName,
  action,
  open,
  onClose,
  onConfirm,
}: ApprovalDialogProps) {
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const isApprove = action === "approve";
  const title = isApprove ? "Approve Task" : "Reject Task";
  const buttonLabel = isApprove ? "Approve" : "Reject";
  const buttonColor = isApprove
    ? "bg-green-600 hover:bg-green-700 focus:ring-green-500"
    : "bg-red-600 hover:bg-red-700 focus:ring-red-500";

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      onConfirm(comment);
    } finally {
      setSubmitting(false);
      setComment("");
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-dialog-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black bg-opacity-40"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h2
          id="approval-dialog-title"
          className="text-lg font-semibold text-gray-900 mb-1"
        >
          {title}
        </h2>
        <p className="text-sm text-gray-500 mb-4">
          {isApprove ? "Approve" : "Reject"} task:{" "}
          <span className="font-medium text-gray-700">{taskName}</span>
        </p>

        <label
          htmlFor="approval-comment"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Comment {!isApprove && <span className="text-red-500">*</span>}
        </label>
        <textarea
          id="approval-comment"
          className="
            w-full rounded-md border border-gray-300 px-3 py-2 text-sm
            placeholder-gray-400 focus:outline-none focus:ring-2
            focus:ring-offset-1 focus:ring-blue-500
          "
          rows={3}
          placeholder={
            isApprove
              ? "Optional comment..."
              : "Explain why this task is being rejected..."
          }
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />

        <div className="flex justify-end gap-3 mt-4">
          <button
            type="button"
            className="
              px-4 py-2 text-sm font-medium text-gray-700
              bg-white border border-gray-300 rounded-md
              hover:bg-gray-50 focus:outline-none focus:ring-2
              focus:ring-offset-1 focus:ring-gray-400
            "
            onClick={() => {
              setComment("");
              onClose();
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            className={`
              px-4 py-2 text-sm font-medium text-white rounded-md
              focus:outline-none focus:ring-2 focus:ring-offset-1
              disabled:opacity-50
              ${buttonColor}
            `}
            disabled={submitting || (!isApprove && comment.trim().length === 0)}
            onClick={handleSubmit}
          >
            {submitting ? "..." : buttonLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
