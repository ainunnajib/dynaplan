import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import (
    ApprovalDecision,
    TaskStatus,
    Workflow,
    WorkflowApproval,
    WorkflowStage,
    WorkflowStatus,
    WorkflowTask,
)
from app.schemas.workflow import (
    ApprovalCreate,
    StageCreate,
    StageUpdate,
    TaskCreate,
    TaskUpdate,
    WorkflowCreate,
    WorkflowProgress,
    WorkflowUpdate,
)


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------


async def create_workflow(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    data: WorkflowCreate,
) -> Workflow:
    workflow = Workflow(
        model_id=model_id,
        created_by=user_id,
        name=data.name,
        description=data.description,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflow_by_id(
    db: AsyncSession, workflow_id: uuid.UUID
) -> Optional[Workflow]:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id)
    )
    return result.scalar_one_or_none()


async def list_workflows_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[Workflow]:
    result = await db.execute(
        select(Workflow)
        .where(Workflow.model_id == model_id)
        .order_by(Workflow.created_at.asc())
    )
    return list(result.scalars().all())


async def update_workflow(
    db: AsyncSession, workflow: Workflow, data: WorkflowUpdate
) -> Workflow:
    if data.name is not None:
        workflow.name = data.name
    if data.description is not None:
        workflow.description = data.description
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(db: AsyncSession, workflow: Workflow) -> None:
    await db.delete(workflow)
    await db.commit()


# ---------------------------------------------------------------------------
# Workflow status transitions
# ---------------------------------------------------------------------------


async def activate_workflow(db: AsyncSession, workflow: Workflow) -> Workflow:
    if workflow.status != WorkflowStatus.draft:
        raise ValueError("Only draft workflows can be activated")
    workflow.status = WorkflowStatus.active
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def complete_workflow(db: AsyncSession, workflow: Workflow) -> Workflow:
    if workflow.status != WorkflowStatus.active:
        raise ValueError("Only active workflows can be completed")
    workflow.status = WorkflowStatus.completed
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def archive_workflow(db: AsyncSession, workflow: Workflow) -> Workflow:
    workflow.status = WorkflowStatus.archived
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


# ---------------------------------------------------------------------------
# Stage CRUD
# ---------------------------------------------------------------------------


async def create_stage(
    db: AsyncSession, workflow_id: uuid.UUID, data: StageCreate
) -> WorkflowStage:
    stage = WorkflowStage(
        workflow_id=workflow_id,
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
        is_gate=data.is_gate,
    )
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return stage


async def get_stage_by_id(
    db: AsyncSession, stage_id: uuid.UUID
) -> Optional[WorkflowStage]:
    result = await db.execute(
        select(WorkflowStage).where(WorkflowStage.id == stage_id)
    )
    return result.scalar_one_or_none()


async def update_stage(
    db: AsyncSession, stage: WorkflowStage, data: StageUpdate
) -> WorkflowStage:
    if data.name is not None:
        stage.name = data.name
    if data.description is not None:
        stage.description = data.description
    if data.sort_order is not None:
        stage.sort_order = data.sort_order
    if data.is_gate is not None:
        stage.is_gate = data.is_gate
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return stage


async def delete_stage(db: AsyncSession, stage: WorkflowStage) -> None:
    await db.delete(stage)
    await db.commit()


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------


async def create_task(
    db: AsyncSession, stage_id: uuid.UUID, data: TaskCreate
) -> WorkflowTask:
    task = WorkflowTask(
        stage_id=stage_id,
        name=data.name,
        description=data.description,
        assignee_id=data.assignee_id,
        due_date=data.due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_by_id(
    db: AsyncSession, task_id: uuid.UUID
) -> Optional[WorkflowTask]:
    result = await db.execute(
        select(WorkflowTask).where(WorkflowTask.id == task_id)
    )
    return result.scalar_one_or_none()


async def update_task(
    db: AsyncSession, task: WorkflowTask, data: TaskUpdate
) -> WorkflowTask:
    if data.name is not None:
        task.name = data.name
    if data.description is not None:
        task.description = data.description
    if data.assignee_id is not None:
        task.assignee_id = data.assignee_id
    if data.due_date is not None:
        task.due_date = data.due_date
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Task status transitions
# ---------------------------------------------------------------------------

# Valid transitions: pending -> in_progress -> submitted -> approved/rejected
# rejected -> in_progress (resubmit flow)

VALID_TRANSITIONS = {
    TaskStatus.pending: {TaskStatus.in_progress},
    TaskStatus.in_progress: {TaskStatus.submitted},
    TaskStatus.submitted: {TaskStatus.approved, TaskStatus.rejected},
    TaskStatus.rejected: {TaskStatus.in_progress},
    TaskStatus.approved: set(),
}


async def transition_task_status(
    db: AsyncSession, task: WorkflowTask, new_status: TaskStatus
) -> WorkflowTask:
    allowed = VALID_TRANSITIONS.get(task.status, set())
    if new_status not in allowed:
        raise ValueError(
            f"Cannot transition from {task.status.value} to {new_status.value}"
        )
    task.status = new_status
    if new_status == TaskStatus.approved:
        task.completed_at = datetime.now(timezone.utc)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def submit_task(db: AsyncSession, task: WorkflowTask) -> WorkflowTask:
    return await transition_task_status(db, task, TaskStatus.submitted)


async def approve_task(
    db: AsyncSession,
    task: WorkflowTask,
    approver_id: uuid.UUID,
    data: ApprovalCreate,
) -> WorkflowTask:
    if task.status != TaskStatus.submitted:
        raise ValueError("Only submitted tasks can be approved")
    approval = WorkflowApproval(
        task_id=task.id,
        approver_id=approver_id,
        decision=ApprovalDecision.approved,
        comment=data.comment,
    )
    db.add(approval)
    task.status = TaskStatus.approved
    task.completed_at = datetime.now(timezone.utc)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def reject_task(
    db: AsyncSession,
    task: WorkflowTask,
    approver_id: uuid.UUID,
    data: ApprovalCreate,
) -> WorkflowTask:
    if task.status != TaskStatus.submitted:
        raise ValueError("Only submitted tasks can be rejected")
    approval = WorkflowApproval(
        task_id=task.id,
        approver_id=approver_id,
        decision=ApprovalDecision.rejected,
        comment=data.comment,
    )
    db.add(approval)
    task.status = TaskStatus.rejected
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Gate check
# ---------------------------------------------------------------------------


async def is_gate_stage_completed(
    db: AsyncSession, stage: WorkflowStage
) -> bool:
    """Check if all tasks in a gate stage are approved."""
    if not stage.is_gate:
        return False
    result = await db.execute(
        select(WorkflowTask).where(WorkflowTask.stage_id == stage.id)
    )
    tasks = list(result.scalars().all())
    if len(tasks) == 0:
        return False
    return all(t.status == TaskStatus.approved for t in tasks)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


async def get_workflow_progress(
    db: AsyncSession, workflow: Workflow
) -> WorkflowProgress:
    # Refresh stages and tasks
    await db.refresh(workflow)
    total_tasks = 0
    tasks_by_status = {s.value: 0 for s in TaskStatus}
    gate_total = 0
    gate_completed = 0

    for stage in workflow.stages:
        if stage.is_gate:
            gate_total += 1
        stage_all_approved = True
        stage_has_tasks = False
        for task in stage.tasks:
            total_tasks += 1
            tasks_by_status[task.status.value] = tasks_by_status.get(task.status.value, 0) + 1
            if task.status != TaskStatus.approved:
                stage_all_approved = False
            stage_has_tasks = True
        if stage.is_gate and stage_has_tasks and stage_all_approved:
            gate_completed += 1

    return WorkflowProgress(
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        status=workflow.status.value,
        total_stages=len(workflow.stages),
        total_tasks=total_tasks,
        tasks_by_status=tasks_by_status,
        gate_stages_completed=gate_completed,
        gate_stages_total=gate_total,
    )
