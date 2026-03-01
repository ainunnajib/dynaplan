"use client";

import { useState } from "react";

export interface WorkflowTaskData {
  id: string;
  stage_id: string;
  name: string;
  description: string | null;
  assignee_id: string | null;
  status: "pending" | "in_progress" | "submitted" | "approved" | "rejected";
  due_date: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending: { bg: "bg-gray-100", text: "text-gray-700", label: "Pending" },
  in_progress: { bg: "bg-blue-100", text: "text-blue-700", label: "In Progress" },
  submitted: { bg: "bg-yellow-100", text: "text-yellow-700", label: "Submitted" },
  approved: { bg: "bg-green-100", text: "text-green-700", label: "Approved" },
  rejected: { bg: "bg-red-100", text: "text-red-700", label: "Rejected" },
};

interface TaskCardProps {
  task: WorkflowTaskData;
  onApprove?: (taskId: string) => void;
  onReject?: (taskId: string) => void;
  onSubmit?: (taskId: string) => void;
  onClick?: (task: WorkflowTaskData) => void;
}

export function TaskCard({ task, onApprove, onReject, onSubmit, onClick }: TaskCardProps) {
  const style = STATUS_STYLES[task.status] ?? STATUS_STYLES.pending;
  const [isHovered, setIsHovered] = useState(false);

  const formattedDueDate = task.due_date
    ? new Date(task.due_date).toLocaleDateString()
    : null;

  return (
    <div
      className={`
        border rounded-lg p-3 mb-2 cursor-pointer transition-shadow
        ${isHovered ? "shadow-md" : "shadow-sm"}
        bg-white
      `}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => onClick?.(task)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onClick?.(task);
        }
      }}
    >
      <div className="flex items-start justify-between mb-1">
        <h4 className="text-sm font-medium text-gray-900 truncate flex-1">
          {task.name}
        </h4>
        <span
          className={`
            ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium
            ${style.bg} ${style.text}
          `}
        >
          {style.label}
        </span>
      </div>

      {task.description && (
        <p className="text-xs text-gray-500 mb-2 line-clamp-2">
          {task.description}
        </p>
      )}

      <div className="flex items-center justify-between">
        {formattedDueDate && (
          <span className="text-xs text-gray-400">
            Due: {formattedDueDate}
          </span>
        )}
        <div className="flex gap-1 ml-auto">
          {task.status === "in_progress" && onSubmit && (
            <button
              type="button"
              className="text-xs px-2 py-1 rounded bg-yellow-500 text-white hover:bg-yellow-600"
              onClick={(e) => {
                e.stopPropagation();
                onSubmit(task.id);
              }}
            >
              Submit
            </button>
          )}
          {task.status === "submitted" && onApprove && (
            <button
              type="button"
              className="text-xs px-2 py-1 rounded bg-green-500 text-white hover:bg-green-600"
              onClick={(e) => {
                e.stopPropagation();
                onApprove(task.id);
              }}
            >
              Approve
            </button>
          )}
          {task.status === "submitted" && onReject && (
            <button
              type="button"
              className="text-xs px-2 py-1 rounded bg-red-500 text-white hover:bg-red-600"
              onClick={(e) => {
                e.stopPropagation();
                onReject(task.id);
              }}
            >
              Reject
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
