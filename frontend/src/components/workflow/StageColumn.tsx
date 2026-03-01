"use client";

import { TaskCard, WorkflowTaskData } from "./TaskCard";

export interface WorkflowStageData {
  id: string;
  workflow_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  is_gate: boolean;
  created_at: string;
  tasks: WorkflowTaskData[];
}

interface StageColumnProps {
  stage: WorkflowStageData;
  onTaskClick?: (task: WorkflowTaskData) => void;
  onApproveTask?: (taskId: string) => void;
  onRejectTask?: (taskId: string) => void;
  onSubmitTask?: (taskId: string) => void;
}

export function StageColumn({
  stage,
  onTaskClick,
  onApproveTask,
  onRejectTask,
  onSubmitTask,
}: StageColumnProps) {
  const approvedCount = stage.tasks.filter((t) => t.status === "approved").length;
  const totalCount = stage.tasks.length;

  return (
    <div className="flex flex-col w-72 min-w-[18rem] bg-gray-50 rounded-lg border border-gray-200">
      {/* Header */}
      <div className="p-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {stage.name}
          </h3>
          {stage.is_gate && (
            <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
              Gate
            </span>
          )}
        </div>
        {stage.description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
            {stage.description}
          </p>
        )}
        <div className="mt-2 flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-500 rounded-full transition-all"
              style={{
                width: totalCount > 0 ? `${(approvedCount / totalCount) * 100}%` : "0%",
              }}
            />
          </div>
          <span className="text-xs text-gray-500">
            {approvedCount}/{totalCount}
          </span>
        </div>
      </div>

      {/* Task list */}
      <div className="p-2 flex-1 overflow-y-auto max-h-[calc(100vh-16rem)]">
        {stage.tasks.length === 0 ? (
          <p className="text-xs text-gray-400 text-center py-4">No tasks yet</p>
        ) : (
          stage.tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onClick={onTaskClick}
              onApprove={onApproveTask}
              onReject={onRejectTask}
              onSubmit={onSubmitTask}
            />
          ))
        )}
      </div>
    </div>
  );
}
