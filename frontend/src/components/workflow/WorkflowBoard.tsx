"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { StageColumn, WorkflowStageData } from "./StageColumn";
import { WorkflowTaskData } from "./TaskCard";
import { ApprovalDialog } from "./ApprovalDialog";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface WorkflowDetail {
  id: string;
  model_id: string;
  name: string;
  description: string | null;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  stages: WorkflowStageData[];
}

interface WorkflowBoardProps {
  workflowId: string;
}

export function WorkflowBoard({ workflowId }: WorkflowBoardProps) {
  const { token } = useAuth();
  const [workflow, setWorkflow] = useState<WorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Approval dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<"approve" | "reject">("approve");
  const [dialogTask, setDialogTask] = useState<WorkflowTaskData | null>(null);

  const fetchWorkflow = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/workflows/${workflowId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError("Failed to load workflow");
        return;
      }
      const data = (await res.json()) as WorkflowDetail;
      setWorkflow(data);
      setError(null);
    } catch {
      setError("Network error");
    } finally {
      setLoading(false);
    }
  }, [token, workflowId]);

  useEffect(() => {
    void fetchWorkflow();
  }, [fetchWorkflow]);

  const handleSubmitTask = useCallback(
    async (taskId: string) => {
      if (!token) return;
      try {
        const res = await fetch(`${API_BASE}/tasks/${taskId}/submit`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          void fetchWorkflow();
        }
      } catch {
        // Silently ignore
      }
    },
    [token, fetchWorkflow],
  );

  const openApprovalDialog = useCallback(
    (taskId: string, action: "approve" | "reject") => {
      if (!workflow) return;
      for (const stage of workflow.stages) {
        const task = stage.tasks.find((t) => t.id === taskId);
        if (task) {
          setDialogTask(task);
          setDialogAction(action);
          setDialogOpen(true);
          return;
        }
      }
    },
    [workflow],
  );

  const handleApproveTask = useCallback(
    (taskId: string) => openApprovalDialog(taskId, "approve"),
    [openApprovalDialog],
  );

  const handleRejectTask = useCallback(
    (taskId: string) => openApprovalDialog(taskId, "reject"),
    [openApprovalDialog],
  );

  const handleDialogConfirm = useCallback(
    async (comment: string) => {
      if (!token || !dialogTask) return;
      const endpoint =
        dialogAction === "approve"
          ? `${API_BASE}/tasks/${dialogTask.id}/approve`
          : `${API_BASE}/tasks/${dialogTask.id}/reject`;
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ comment }),
        });
        if (res.ok) {
          void fetchWorkflow();
        }
      } catch {
        // Silently ignore
      } finally {
        setDialogOpen(false);
        setDialogTask(null);
      }
    },
    [token, dialogTask, dialogAction, fetchWorkflow],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-gray-500">Loading workflow...</p>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-sm text-red-500">{error ?? "Workflow not found"}</p>
      </div>
    );
  }

  const STATUS_BADGE: Record<string, string> = {
    draft: "bg-gray-100 text-gray-700",
    active: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    archived: "bg-yellow-100 text-yellow-700",
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{workflow.name}</h2>
          {workflow.description && (
            <p className="text-sm text-gray-500 mt-0.5">{workflow.description}</p>
          )}
        </div>
        <span
          className={`
            inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium
            ${STATUS_BADGE[workflow.status] ?? STATUS_BADGE.draft}
          `}
        >
          {workflow.status.charAt(0).toUpperCase() + workflow.status.slice(1)}
        </span>
      </div>

      {/* Kanban board */}
      <div className="flex-1 overflow-x-auto p-4">
        <div className="flex gap-4 h-full">
          {workflow.stages.length === 0 ? (
            <p className="text-sm text-gray-400 m-auto">
              No stages defined. Add stages to this workflow to get started.
            </p>
          ) : (
            workflow.stages.map((stage) => (
              <StageColumn
                key={stage.id}
                stage={stage}
                onSubmitTask={handleSubmitTask}
                onApproveTask={handleApproveTask}
                onRejectTask={handleRejectTask}
              />
            ))
          )}
        </div>
      </div>

      {/* Approval/Reject dialog */}
      {dialogTask && (
        <ApprovalDialog
          taskName={dialogTask.name}
          action={dialogAction}
          open={dialogOpen}
          onClose={() => {
            setDialogOpen(false);
            setDialogTask(null);
          }}
          onConfirm={handleDialogConfirm}
        />
      )}
    </div>
  );
}
