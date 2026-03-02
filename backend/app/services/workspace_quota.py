import uuid
from typing import Dict, List, Optional, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cell import CellValue
from app.models.dimension import Dimension
from app.models.module import LineItem, Module
from app.models.planning_model import PlanningModel
from app.models.workspace_quota import WorkspaceQuota

DEFAULT_MAX_MODELS = 100
DEFAULT_MAX_CELLS_PER_MODEL = 1_000_000
DEFAULT_MAX_DIMENSIONS_PER_MODEL = 200
DEFAULT_STORAGE_LIMIT_MB = 1024


class WorkspaceQuotaError(ValueError):
    """Base error type for workspace quota operations."""


class WorkspaceQuotaExceededError(WorkspaceQuotaError):
    """Raised when a create/write operation would exceed quota."""


class WorkspaceQuotaValidationError(WorkspaceQuotaError):
    """Raised when quota configuration is invalid."""


def _validate_quota_value(name: str, value: Optional[int]) -> None:
    if value is not None and value <= 0:
        raise WorkspaceQuotaValidationError(f"{name} must be greater than 0")


async def create_default_workspace_quota(
    db: AsyncSession, workspace_id: uuid.UUID
) -> WorkspaceQuota:
    quota = WorkspaceQuota(
        workspace_id=workspace_id,
        max_models=DEFAULT_MAX_MODELS,
        max_cells_per_model=DEFAULT_MAX_CELLS_PER_MODEL,
        max_dimensions_per_model=DEFAULT_MAX_DIMENSIONS_PER_MODEL,
        storage_limit_mb=DEFAULT_STORAGE_LIMIT_MB,
    )
    db.add(quota)
    await db.commit()
    await db.refresh(quota)
    return quota


async def get_workspace_quota(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Optional[WorkspaceQuota]:
    result = await db.execute(
        select(WorkspaceQuota).where(WorkspaceQuota.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def ensure_workspace_quota(
    db: AsyncSession, workspace_id: uuid.UUID
) -> WorkspaceQuota:
    quota = await get_workspace_quota(db, workspace_id)
    if quota is not None:
        return quota
    return await create_default_workspace_quota(db, workspace_id)


async def get_workspace_quota_limits(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Tuple[int, int, int, int]:
    quota = await get_workspace_quota(db, workspace_id)
    if quota is None:
        return (
            DEFAULT_MAX_MODELS,
            DEFAULT_MAX_CELLS_PER_MODEL,
            DEFAULT_MAX_DIMENSIONS_PER_MODEL,
            DEFAULT_STORAGE_LIMIT_MB,
        )
    return (
        int(quota.max_models),
        int(quota.max_cells_per_model),
        int(quota.max_dimensions_per_model),
        int(quota.storage_limit_mb),
    )


async def update_workspace_quota(
    db: AsyncSession,
    quota: WorkspaceQuota,
    *,
    max_models: Optional[int] = None,
    max_cells_per_model: Optional[int] = None,
    max_dimensions_per_model: Optional[int] = None,
    storage_limit_mb: Optional[int] = None,
) -> WorkspaceQuota:
    _validate_quota_value("max_models", max_models)
    _validate_quota_value("max_cells_per_model", max_cells_per_model)
    _validate_quota_value("max_dimensions_per_model", max_dimensions_per_model)
    _validate_quota_value("storage_limit_mb", storage_limit_mb)

    if max_models is not None:
        quota.max_models = max_models
    if max_cells_per_model is not None:
        quota.max_cells_per_model = max_cells_per_model
    if max_dimensions_per_model is not None:
        quota.max_dimensions_per_model = max_dimensions_per_model
    if storage_limit_mb is not None:
        quota.storage_limit_mb = storage_limit_mb

    await db.commit()
    await db.refresh(quota)
    return quota


def estimate_cell_storage_bytes(
    dimension_key: str,
    value_number: Optional[float],
    value_text: Optional[str],
    value_boolean: Optional[bool],
    value_encrypted: Optional[str] = None,
) -> int:
    size = len((dimension_key or "").encode("utf-8"))
    if value_encrypted is not None:
        size += len(value_encrypted.encode("utf-8"))
    elif value_text is not None:
        size += len(value_text.encode("utf-8"))
    elif value_number is not None:
        size += 8
    elif value_boolean is not None:
        size += 1
    return size


def estimate_existing_cell_storage_bytes(cell: CellValue) -> int:
    return estimate_cell_storage_bytes(
        dimension_key=cell.dimension_key,
        value_number=cell.value_number,
        value_text=cell.value_text,
        value_boolean=cell.value_boolean,
        value_encrypted=cell.value_encrypted,
    )


def _cell_storage_expr():
    return (
        func.coalesce(func.length(CellValue.dimension_key), 0)
        + case(
            (CellValue.value_encrypted.is_not(None), func.length(CellValue.value_encrypted)),
            else_=0,
        )
        + case(
            (CellValue.value_text.is_not(None), func.length(CellValue.value_text)),
            else_=0,
        )
        + case((CellValue.value_number.is_not(None), 8), else_=0)
        + case((CellValue.value_boolean.is_not(None), 1), else_=0)
    )


async def _count_models_for_workspace(
    db: AsyncSession, workspace_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(PlanningModel)
        .where(PlanningModel.workspace_id == workspace_id)
    )
    return int(result.scalar_one() or 0)


async def _count_dimensions_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Dimension)
        .where(Dimension.model_id == model_id)
    )
    return int(result.scalar_one() or 0)


async def _count_cells_for_model(
    db: AsyncSession, model_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(CellValue)
        .join(LineItem, LineItem.id == CellValue.line_item_id)
        .join(Module, Module.id == LineItem.module_id)
        .where(Module.model_id == model_id)
    )
    return int(result.scalar_one() or 0)


async def _storage_used_for_model_bytes(
    db: AsyncSession, model_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(_cell_storage_expr()), 0))
        .select_from(CellValue)
        .join(LineItem, LineItem.id == CellValue.line_item_id)
        .join(Module, Module.id == LineItem.module_id)
        .where(Module.model_id == model_id)
    )
    return int(result.scalar_one() or 0)


async def _storage_used_for_workspace_bytes(
    db: AsyncSession, workspace_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(_cell_storage_expr()), 0))
        .select_from(CellValue)
        .join(LineItem, LineItem.id == CellValue.line_item_id)
        .join(Module, Module.id == LineItem.module_id)
        .join(PlanningModel, PlanningModel.id == Module.model_id)
        .where(PlanningModel.workspace_id == workspace_id)
    )
    return int(result.scalar_one() or 0)


async def enforce_model_creation_quota(
    db: AsyncSession, workspace_id: uuid.UUID
) -> None:
    max_models, _, _, _ = await get_workspace_quota_limits(db, workspace_id)
    existing_models = await _count_models_for_workspace(db, workspace_id)
    if existing_models >= max_models:
        raise WorkspaceQuotaExceededError(
            f"Workspace model quota exceeded ({existing_models}/{max_models})"
        )


async def enforce_dimension_creation_quota(
    db: AsyncSession, model_id: uuid.UUID
) -> None:
    model_result = await db.execute(
        select(PlanningModel.workspace_id).where(PlanningModel.id == model_id)
    )
    workspace_id = model_result.scalar_one_or_none()
    if workspace_id is None:
        return

    _, _, max_dimensions_per_model, _ = await get_workspace_quota_limits(
        db, workspace_id
    )
    existing_dimensions = await _count_dimensions_for_model(db, model_id)
    if existing_dimensions >= max_dimensions_per_model:
        raise WorkspaceQuotaExceededError(
            "Model dimension quota exceeded "
            f"({existing_dimensions}/{max_dimensions_per_model})"
        )


async def _resolve_line_item_scope(
    db: AsyncSession, line_item_id: uuid.UUID
) -> Optional[Tuple[uuid.UUID, uuid.UUID]]:
    result = await db.execute(
        select(Module.model_id, PlanningModel.workspace_id)
        .select_from(LineItem)
        .join(Module, Module.id == LineItem.module_id)
        .join(PlanningModel, PlanningModel.id == Module.model_id)
        .where(LineItem.id == line_item_id)
    )
    row = result.first()
    if row is None:
        return None
    return row[0], row[1]


async def enforce_cell_write_quota(
    db: AsyncSession,
    line_item_id: uuid.UUID,
    dimension_key: str,
    value_number: Optional[float],
    value_text: Optional[str],
    value_boolean: Optional[bool],
    existing_cell: Optional[CellValue],
) -> None:
    scope = await _resolve_line_item_scope(db, line_item_id)
    if scope is None:
        return
    model_id, workspace_id = scope

    _, max_cells_per_model, _, storage_limit_mb = await get_workspace_quota_limits(
        db, workspace_id
    )

    if existing_cell is None:
        existing_cells = await _count_cells_for_model(db, model_id)
        if existing_cells >= max_cells_per_model:
            raise WorkspaceQuotaExceededError(
                "Model cell quota exceeded "
                f"({existing_cells}/{max_cells_per_model})"
            )

    current_storage = await _storage_used_for_workspace_bytes(db, workspace_id)
    existing_size = (
        estimate_existing_cell_storage_bytes(existing_cell)
        if existing_cell is not None
        else 0
    )
    new_size = estimate_cell_storage_bytes(
        dimension_key=dimension_key,
        value_number=value_number,
        value_text=value_text,
        value_boolean=value_boolean,
    )
    projected_storage = current_storage - existing_size + new_size
    storage_limit_bytes = storage_limit_mb * 1024 * 1024
    if projected_storage > storage_limit_bytes:
        raise WorkspaceQuotaExceededError(
            "Workspace storage quota exceeded "
            f"({projected_storage} bytes/{storage_limit_bytes} bytes)"
        )


def _bytes_to_mb(size_bytes: int) -> float:
    return round(size_bytes / (1024.0 * 1024.0), 4)


async def get_workspace_quota_usage(
    db: AsyncSession, workspace_id: uuid.UUID
) -> Dict[str, object]:
    quota = await ensure_workspace_quota(db, workspace_id)
    models_result = await db.execute(
        select(PlanningModel.id, PlanningModel.name)
        .where(PlanningModel.workspace_id == workspace_id)
        .order_by(PlanningModel.created_at.asc())
    )
    model_rows = models_result.all()

    model_usage: List[Dict[str, object]] = []
    total_dimensions = 0
    total_cells = 0
    total_storage_bytes = 0

    for model_id, model_name in model_rows:
        dimension_count = await _count_dimensions_for_model(db, model_id)
        cell_count = await _count_cells_for_model(db, model_id)
        storage_used_bytes = await _storage_used_for_model_bytes(db, model_id)
        total_dimensions += dimension_count
        total_cells += cell_count
        total_storage_bytes += storage_used_bytes

        model_usage.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "dimension_count": dimension_count,
                "cell_count": cell_count,
                "storage_used_bytes": storage_used_bytes,
                "storage_used_mb": _bytes_to_mb(storage_used_bytes),
            }
        )

    return {
        "workspace_id": workspace_id,
        "max_models": int(quota.max_models),
        "max_cells_per_model": int(quota.max_cells_per_model),
        "max_dimensions_per_model": int(quota.max_dimensions_per_model),
        "storage_limit_mb": int(quota.storage_limit_mb),
        "model_count": len(model_rows),
        "total_dimension_count": total_dimensions,
        "total_cell_count": total_cells,
        "storage_used_bytes": total_storage_bytes,
        "storage_used_mb": _bytes_to_mb(total_storage_bytes),
        "models": model_usage,
    }
