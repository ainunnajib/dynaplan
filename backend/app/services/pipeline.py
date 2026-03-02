import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.pipeline_runtime import PipelineRuntimeExecutor

from app.models.pipeline import (
    Pipeline,
    PipelineRun,
    PipelineRunStatus,
    PipelineStep,
    PipelineStepLog,
    StepLogStatus,
    StepType,
)
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineStepCreate,
    PipelineStepUpdate,
    PipelineUpdate,
    PipelineValidationResult,
    StepReorderRequest,
)


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------


async def create_pipeline(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    data: PipelineCreate,
) -> Pipeline:
    pipeline = Pipeline(
        model_id=model_id,
        created_by=user_id,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


async def get_pipeline_by_id(
    db: AsyncSession, pipeline_id: uuid.UUID
) -> Optional[Pipeline]:
    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.id == pipeline_id)
        .options(selectinload(Pipeline.steps))
    )
    return result.scalar_one_or_none()


async def list_pipelines_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> List[Pipeline]:
    result = await db.execute(
        select(Pipeline)
        .where(Pipeline.model_id == model_id)
        .order_by(Pipeline.created_at.asc())
    )
    return list(result.scalars().all())


async def update_pipeline(
    db: AsyncSession, pipeline: Pipeline, data: PipelineUpdate
) -> Pipeline:
    if data.name is not None:
        pipeline.name = data.name
    if data.description is not None:
        pipeline.description = data.description
    if data.is_active is not None:
        pipeline.is_active = data.is_active
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return pipeline


async def delete_pipeline(db: AsyncSession, pipeline: Pipeline) -> None:
    await db.delete(pipeline)
    await db.commit()


# ---------------------------------------------------------------------------
# PipelineStep CRUD
# ---------------------------------------------------------------------------


async def create_step(
    db: AsyncSession, pipeline_id: uuid.UUID, data: PipelineStepCreate
) -> PipelineStep:
    # Validate step_type
    try:
        step_type_enum = StepType(data.step_type)
    except ValueError:
        raise ValueError(
            f"Invalid step_type '{data.step_type}'. "
            f"Must be one of: {[t.value for t in StepType]}"
        )
    step = PipelineStep(
        pipeline_id=pipeline_id,
        name=data.name,
        step_type=step_type_enum,
        config=data.config,
        sort_order=data.sort_order,
    )
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def get_step_by_id(
    db: AsyncSession, step_id: uuid.UUID
) -> Optional[PipelineStep]:
    result = await db.execute(
        select(PipelineStep).where(PipelineStep.id == step_id)
    )
    return result.scalar_one_or_none()


async def update_step(
    db: AsyncSession, step: PipelineStep, data: PipelineStepUpdate
) -> PipelineStep:
    if data.name is not None:
        step.name = data.name
    if data.step_type is not None:
        try:
            step.step_type = StepType(data.step_type)
        except ValueError:
            raise ValueError(
                f"Invalid step_type '{data.step_type}'. "
                f"Must be one of: {[t.value for t in StepType]}"
            )
    if data.config is not None:
        step.config = data.config
    if data.sort_order is not None:
        step.sort_order = data.sort_order
    db.add(step)
    await db.commit()
    await db.refresh(step)
    return step


async def delete_step(db: AsyncSession, step: PipelineStep) -> None:
    await db.delete(step)
    await db.commit()


async def reorder_steps(
    db: AsyncSession, pipeline_id: uuid.UUID, data: StepReorderRequest
) -> List[PipelineStep]:
    for item in data.steps:
        result = await db.execute(
            select(PipelineStep).where(
                PipelineStep.id == item.step_id,
                PipelineStep.pipeline_id == pipeline_id,
            )
        )
        step = result.scalar_one_or_none()
        if step is None:
            raise ValueError(f"Step {item.step_id} not found in pipeline {pipeline_id}")
        step.sort_order = item.sort_order
        db.add(step)
    await db.commit()

    # Return updated steps
    result = await db.execute(
        select(PipelineStep)
        .where(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.sort_order)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Pipeline Run
# ---------------------------------------------------------------------------


async def trigger_pipeline_run(
    db: AsyncSession, pipeline: Pipeline, user_id: uuid.UUID
) -> PipelineRun:
    if not pipeline.is_active:
        raise ValueError("Cannot trigger an inactive pipeline")

    # Get steps ordered by sort_order
    result = await db.execute(
        select(PipelineStep)
        .where(PipelineStep.pipeline_id == pipeline.id)
        .order_by(PipelineStep.sort_order)
    )
    steps = list(result.scalars().all())

    if len(steps) == 0:
        raise ValueError("Cannot trigger a pipeline with no steps")

    run = PipelineRun(
        pipeline_id=pipeline.id,
        triggered_by=user_id,
        status=PipelineRunStatus.pending,
        total_steps=len(steps),
        completed_steps=0,
    )
    db.add(run)
    await db.flush()

    # Create step logs for each step
    for step in steps:
        log = PipelineStepLog(
            run_id=run.id,
            step_id=step.id,
            status=StepLogStatus.pending,
        )
        db.add(log)

    await db.commit()
    await db.refresh(run)
    return run


async def get_run_by_id(
    db: AsyncSession, run_id: uuid.UUID
) -> Optional[PipelineRun]:
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.id == run_id)
        .options(
            selectinload(PipelineRun.pipeline).selectinload(Pipeline.steps),
            selectinload(PipelineRun.step_logs),
        )
    )
    return result.scalar_one_or_none()


async def list_runs_for_pipeline(
    db: AsyncSession, pipeline_id: uuid.UUID
) -> List[PipelineRun]:
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.created_at.desc())
    )
    return list(result.scalars().all())


async def start_run(db: AsyncSession, run: PipelineRun) -> PipelineRun:
    if run.status != PipelineRunStatus.pending:
        raise ValueError("Only pending runs can be started")
    run.status = PipelineRunStatus.running
    run.started_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def complete_run(db: AsyncSession, run: PipelineRun) -> PipelineRun:
    if run.status != PipelineRunStatus.running:
        raise ValueError("Only running runs can be completed")
    run.status = PipelineRunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def fail_run(
    db: AsyncSession,
    run: PipelineRun,
    error_step_id: Optional[uuid.UUID] = None,
    error_message: Optional[str] = None,
) -> PipelineRun:
    if run.status != PipelineRunStatus.running:
        raise ValueError("Only running runs can be failed")
    run.status = PipelineRunStatus.failed
    run.error_step_id = error_step_id
    run.error_message = error_message
    run.completed_at = datetime.now(timezone.utc)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def cancel_run(db: AsyncSession, run: PipelineRun) -> PipelineRun:
    if run.status not in (PipelineRunStatus.pending, PipelineRunStatus.running):
        raise ValueError("Only pending or running runs can be cancelled")
    run.status = PipelineRunStatus.cancelled
    run.completed_at = datetime.now(timezone.utc)

    # Mark pending step logs as skipped
    for log in run.step_logs:
        if log.status == StepLogStatus.pending:
            log.status = StepLogStatus.skipped
            db.add(log)

    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def _mark_remaining_logs_skipped(
    db: AsyncSession,
    run: PipelineRun,
) -> None:
    for log in run.step_logs:
        if log.status == StepLogStatus.pending:
            await update_step_log_status(db, log, StepLogStatus.skipped)


async def execute_run(db: AsyncSession, run: PipelineRun) -> PipelineRun:
    hydrated_run = await get_run_by_id(db, run.id)
    if hydrated_run is None:
        raise ValueError("Run not found")

    if hydrated_run.status not in (PipelineRunStatus.pending, PipelineRunStatus.running):
        raise ValueError("Only pending/running runs can be executed")

    if hydrated_run.pipeline is None:
        raise ValueError("Pipeline was not found for run")

    if hydrated_run.status == PipelineRunStatus.pending:
        hydrated_run = await start_run(db, hydrated_run)

    run_context = await get_run_by_id(db, hydrated_run.id)
    if run_context is None or run_context.pipeline is None:
        raise ValueError("Run context could not be loaded")

    ordered_steps = sorted(run_context.pipeline.steps, key=lambda step: step.sort_order)
    if len(ordered_steps) == 0:
        raise ValueError("Pipeline has no steps")

    step_logs_by_step_id = {
        log.step_id: log for log in run_context.step_logs
    }
    runtime_executor = PipelineRuntimeExecutor(db=db, model_id=run_context.pipeline.model_id)

    current_frame = None
    completed_steps = run_context.completed_steps
    for step in ordered_steps:
        step_log = step_logs_by_step_id.get(step.id)
        if step_log is None:
            step_log = PipelineStepLog(
                run_id=run_context.id,
                step_id=step.id,
                status=StepLogStatus.pending,
            )
            db.add(step_log)
            await db.commit()
            await db.refresh(step_log)

        try:
            await update_step_log_status(
                db,
                step_log,
                StepLogStatus.running,
                records_in=0 if current_frame is None else int(len(current_frame.index)),
                log_output="Executing %s step '%s'" % (step.step_type.value, step.name),
            )
            result = await runtime_executor.execute_step(step=step, input_frame=current_frame)
            current_frame = result.output_frame
            await update_step_log_status(
                db,
                step_log,
                StepLogStatus.completed,
                records_in=result.records_in,
                records_out=result.records_out,
                log_output=result.log_output,
            )
            completed_steps += 1
            latest_run = await get_run_by_id(db, run_context.id)
            if latest_run is None:
                raise ValueError("Run not found while updating progress")
            latest_run.completed_steps = completed_steps
            db.add(latest_run)
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            await update_step_log_status(
                db,
                step_log,
                StepLogStatus.failed,
                log_output=str(exc),
            )
            latest_run = await get_run_by_id(db, run_context.id)
            if latest_run is None:
                raise ValueError("Run not found while handling failure")
            await _mark_remaining_logs_skipped(db, latest_run)
            failed_run = await get_run_by_id(db, run_context.id)
            if failed_run is None:
                raise ValueError("Run not found while failing execution")
            return await fail_run(
                db,
                failed_run,
                error_step_id=step.id,
                error_message=str(exc),
            )

    latest_run = await get_run_by_id(db, run_context.id)
    if latest_run is None:
        raise ValueError("Run not found while completing execution")
    latest_run.completed_steps = latest_run.total_steps
    db.add(latest_run)
    await db.commit()
    refreshed_latest = await get_run_by_id(db, latest_run.id)
    if refreshed_latest is None:
        raise ValueError("Run not found while finalizing execution")
    return await complete_run(db, refreshed_latest)


# ---------------------------------------------------------------------------
# Step Log updates
# ---------------------------------------------------------------------------


async def update_step_log_status(
    db: AsyncSession,
    log: PipelineStepLog,
    status: StepLogStatus,
    records_in: Optional[int] = None,
    records_out: Optional[int] = None,
    log_output: Optional[str] = None,
) -> PipelineStepLog:
    log.status = status
    if status == StepLogStatus.running:
        log.started_at = datetime.now(timezone.utc)
    if status in (StepLogStatus.completed, StepLogStatus.failed, StepLogStatus.skipped):
        log.completed_at = datetime.now(timezone.utc)
    if records_in is not None:
        log.records_in = records_in
    if records_out is not None:
        log.records_out = records_out
    if log_output is not None:
        log.log_output = log_output
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_step_log_by_id(
    db: AsyncSession, log_id: uuid.UUID
) -> Optional[PipelineStepLog]:
    result = await db.execute(
        select(PipelineStepLog).where(PipelineStepLog.id == log_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def validate_pipeline(
    db: AsyncSession, pipeline: Pipeline
) -> PipelineValidationResult:
    errors = []

    # Refresh to get latest steps
    result = await db.execute(
        select(PipelineStep)
        .where(PipelineStep.pipeline_id == pipeline.id)
        .order_by(PipelineStep.sort_order)
    )
    steps = list(result.scalars().all())

    if len(steps) == 0:
        errors.append("Pipeline has no steps")
        return PipelineValidationResult(valid=False, errors=errors)

    # Check that first step is a source
    if steps[0].step_type != StepType.source:
        errors.append("First step must be a source step")

    # Check that last step is a publish step
    if steps[-1].step_type != StepType.publish:
        errors.append("Last step must be a publish step")

    # Check for duplicate sort_order values
    sort_orders = [s.sort_order for s in steps]
    if len(sort_orders) != len(set(sort_orders)):
        errors.append("Steps have duplicate sort_order values")

    # Check step names are not empty
    for step in steps:
        if not step.name or not step.name.strip():
            errors.append(f"Step at sort_order {step.sort_order} has an empty name")

    return PipelineValidationResult(
        valid=len(errors) == 0,
        errors=errors,
    )
