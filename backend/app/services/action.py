import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action, ActionType, Process, ProcessRun, ProcessStatus, ProcessStep
from app.schemas.action import ActionCreate, ActionUpdate, ProcessCreate, ProcessStepCreate, ProcessUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Action CRUD
# ---------------------------------------------------------------------------

async def create_action(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: ActionCreate,
) -> Action:
    action = Action(
        name=data.name,
        model_id=model_id,
        action_type=data.action_type,
        config=data.config or {},
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


async def get_action_by_id(
    db: AsyncSession,
    action_id: uuid.UUID,
) -> Optional[Action]:
    result = await db.execute(select(Action).where(Action.id == action_id))
    return result.scalar_one_or_none()


async def list_actions_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[Action]:
    result = await db.execute(
        select(Action).where(Action.model_id == model_id).order_by(Action.created_at.asc())
    )
    return list(result.scalars().all())


async def update_action(
    db: AsyncSession,
    action: Action,
    data: ActionUpdate,
) -> Action:
    if data.name is not None:
        action.name = data.name
    if data.action_type is not None:
        action.action_type = data.action_type
    if data.config is not None:
        action.config = data.config
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


async def delete_action(db: AsyncSession, action: Action) -> None:
    await db.delete(action)
    await db.commit()


# ---------------------------------------------------------------------------
# Process CRUD
# ---------------------------------------------------------------------------

async def create_process(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: ProcessCreate,
) -> Process:
    process = Process(
        name=data.name,
        model_id=model_id,
        description=data.description,
    )
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return process


async def get_process_by_id(
    db: AsyncSession,
    process_id: uuid.UUID,
) -> Optional[Process]:
    result = await db.execute(select(Process).where(Process.id == process_id))
    return result.scalar_one_or_none()


async def list_processes_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[Process]:
    result = await db.execute(
        select(Process).where(Process.model_id == model_id).order_by(Process.created_at.asc())
    )
    return list(result.scalars().all())


async def update_process(
    db: AsyncSession,
    process: Process,
    data: ProcessUpdate,
) -> Process:
    if data.name is not None:
        process.name = data.name
    if data.description is not None:
        process.description = data.description
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return process


async def delete_process(db: AsyncSession, process: Process) -> None:
    await db.delete(process)
    await db.commit()


# ---------------------------------------------------------------------------
# ProcessStep CRUD
# ---------------------------------------------------------------------------

async def add_process_step(
    db: AsyncSession,
    process_id: uuid.UUID,
    data: ProcessStepCreate,
) -> ProcessStep:
    step = ProcessStep(
        process_id=process_id,
        action_id=data.action_id,
        step_order=data.step_order,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def get_process_step_by_id(
    db: AsyncSession,
    step_id: uuid.UUID,
) -> Optional[ProcessStep]:
    result = await db.execute(select(ProcessStep).where(ProcessStep.id == step_id))
    return result.scalar_one_or_none()


async def remove_process_step(db: AsyncSession, step: ProcessStep) -> None:
    await db.delete(step)
    await db.commit()


# ---------------------------------------------------------------------------
# Process execution
# ---------------------------------------------------------------------------

def _execute_action_placeholder(action: Action) -> dict:
    """
    Placeholder execution for each action type.
    Logs what it would do and returns a result dict.
    """
    action_type = action.action_type
    config = action.config or {}

    if action_type == ActionType.import_data:
        source = config.get("source_module_id", "<unknown>")
        file_path = config.get("file_path", "<unknown>")
        logger.info("PLACEHOLDER: import_data from file=%s into module=%s", file_path, source)
        return {
            "action_id": str(action.id),
            "action_type": action_type,
            "status": "ok",
            "message": f"Would import data from {file_path} into module {source}",
        }
    elif action_type == ActionType.export_data:
        source = config.get("source_module_id", "<unknown>")
        file_path = config.get("file_path", "<unknown>")
        logger.info("PLACEHOLDER: export_data from module=%s to file=%s", source, file_path)
        return {
            "action_id": str(action.id),
            "action_type": action_type,
            "status": "ok",
            "message": f"Would export data from module {source} to {file_path}",
        }
    elif action_type == ActionType.delete_data:
        target = config.get("target_module_id", "<unknown>")
        logger.info("PLACEHOLDER: delete_data in module=%s", target)
        return {
            "action_id": str(action.id),
            "action_type": action_type,
            "status": "ok",
            "message": f"Would delete data in module {target}",
        }
    elif action_type == ActionType.run_formula:
        target = config.get("target_module_id", "<unknown>")
        logger.info("PLACEHOLDER: run_formula in module=%s", target)
        return {
            "action_id": str(action.id),
            "action_type": action_type,
            "status": "ok",
            "message": f"Would run formula recalculation in module {target}",
        }
    elif action_type == ActionType.copy_data:
        source = config.get("source_module_id", "<unknown>")
        target = config.get("target_module_id", "<unknown>")
        logger.info("PLACEHOLDER: copy_data from module=%s to module=%s", source, target)
        return {
            "action_id": str(action.id),
            "action_type": action_type,
            "status": "ok",
            "message": f"Would copy data from module {source} to module {target}",
        }
    else:
        return {
            "action_id": str(action.id),
            "action_type": str(action_type),
            "status": "ok",
            "message": "Unknown action type — no-op",
        }


async def run_process(
    db: AsyncSession,
    process_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
) -> ProcessRun:
    """
    Execute a process synchronously:
    1. Create a ProcessRun record (pending -> running)
    2. Execute each step in step_order
    3. Mark completed or failed
    """
    process = await get_process_by_id(db, process_id)
    if process is None:
        raise ValueError(f"Process {process_id} not found")

    process_run = ProcessRun(
        process_id=process_id,
        status=ProcessStatus.pending,
        triggered_by=user_id,
    )
    db.add(process_run)
    await db.commit()
    await db.refresh(process_run)

    # Mark running
    process_run.status = ProcessStatus.running
    process_run.started_at = datetime.now(timezone.utc)
    db.add(process_run)
    await db.commit()

    step_results = []
    try:
        # Reload process to get steps with selectin
        process = await get_process_by_id(db, process_id)
        sorted_steps = sorted(process.steps, key=lambda s: s.step_order)

        for step in sorted_steps:
            step_result = _execute_action_placeholder(step.action)
            step_results.append({
                "step_id": str(step.id),
                "step_order": step.step_order,
                "action_id": str(step.action_id),
                "action_name": step.action.name,
                "result": step_result,
            })

        process_run.status = ProcessStatus.completed
        process_run.completed_at = datetime.now(timezone.utc)
        process_run.result = {"steps": step_results}

    except Exception as exc:
        logger.exception("Process run %s failed", process_run.id)
        process_run.status = ProcessStatus.failed
        process_run.completed_at = datetime.now(timezone.utc)
        process_run.result = {
            "steps": step_results,
            "error": str(exc),
        }

    db.add(process_run)
    await db.commit()
    await db.refresh(process_run)
    return process_run


async def get_process_runs(
    db: AsyncSession,
    process_id: uuid.UUID,
) -> List[ProcessRun]:
    result = await db.execute(
        select(ProcessRun)
        .where(ProcessRun.process_id == process_id)
        .order_by(ProcessRun.created_at.desc())
    )
    return list(result.scalars().all())
