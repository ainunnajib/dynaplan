import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.dimension import Dimension
from app.models.module import LineItem, Module
from app.schemas.action import ProcessRunResponse
from app.schemas.cell import CellBulkWrite, CellQuery, CellRead, CellWrite
from app.schemas.dimension import DimensionResponse
from app.schemas.import_export import ExportFormat, ImportResult
from app.schemas.pipeline import PipelineRunDetail, PipelineRunResponse, PipelineStepLogResponse
from app.schemas.planning_model import PlanningModelResponse
from app.services.api_key import check_scope, validate_api_key
from app.services.action import get_process_by_id, get_process_runs, run_process
from app.services.cell import read_cells_for_line_item, write_cell, write_cells_bulk
from app.services.dimension import list_dimensions_for_model
from app.services.import_export import export_module_to_csv, export_module_to_excel, import_to_dimension, import_to_module, parse_csv, parse_excel
from app.services.pipeline import execute_run, get_pipeline_by_id, get_run_by_id, trigger_pipeline_run
from app.services.planning_model import get_model_by_id, list_models_for_workspace

router = APIRouter(prefix="/api/v1", tags=["public-api"])


# ── Auth dependency ─────────────────────────────────────────────────────────────

async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate the X-API-Key header and return the associated ApiKey record."""
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    api_key = await validate_api_key(db, raw_key=x_api_key)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
    return api_key


def require_scope(required_scope: str):
    """Return a FastAPI dependency that enforces a specific scope on the API key."""
    async def _check(api_key: ApiKey = Depends(get_api_key)) -> ApiKey:
        if not check_scope(api_key, required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required scope: '{required_scope}'",
            )
        return api_key
    return _check


# ── Import/Export helpers ─────────────────────────────────────────────────────

def _detect_format(filename: Optional[str], content_type: Optional[str]) -> str:
    if filename:
        lower = filename.lower()
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return "xlsx"
        if lower.endswith(".csv"):
            return "csv"
    if content_type and "spreadsheet" in content_type:
        return "xlsx"
    return "csv"


async def _parse_upload_file(file: UploadFile):
    content = await file.read()
    fmt = _detect_format(file.filename, file.content_type)
    if fmt == "xlsx":
        try:
            rows = parse_excel(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to parse Excel file: %s" % exc,
            )
    else:
        try:
            rows = parse_csv(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Failed to parse CSV file: %s" % exc,
            )
    return rows


# ── Models ──────────────────────────────────────────────────────────────────────

@router.get(
    "/models",
    response_model=List[PlanningModelResponse],
    summary="List all models (API key: read:models)",
)
async def public_list_models(
    workspace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    """List all models in a workspace using an API key with read:models scope."""
    models = await list_models_for_workspace(db, workspace_id=workspace_id)
    return models


@router.get(
    "/models/{model_id}",
    response_model=PlanningModelResponse,
    summary="Get a model (API key: read:models)",
)
async def public_get_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    """Get a single model by ID using an API key with read:models scope."""
    model = await get_model_by_id(db, model_id=model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    return model


# ── Dimensions ──────────────────────────────────────────────────────────────────

@router.get(
    "/models/{model_id}/dimensions",
    response_model=List[DimensionResponse],
    summary="List dimensions for a model (API key: read:dimensions)",
)
async def public_list_dimensions(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:dimensions")),
):
    """List all dimensions for a model using an API key with read:dimensions scope."""
    model = await get_model_by_id(db, model_id=model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    dimensions = await list_dimensions_for_model(db, model_id=model_id)
    return dimensions


# ── Cells ───────────────────────────────────────────────────────────────────────

@router.post(
    "/cells/query",
    response_model=List[CellRead],
    summary="Query cells (API key: read:cells)",
)
async def public_query_cells(
    data: CellQuery,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:cells")),
):
    """Query cells for a line item using an API key with read:cells scope."""
    return await read_cells_for_line_item(
        db,
        line_item_id=data.line_item_id,
        version_id=data.version_id,
        dimension_filters=data.dimension_filters,
    )


@router.post(
    "/cells",
    response_model=CellRead,
    status_code=status.HTTP_200_OK,
    summary="Write a single cell (API key: write:cells)",
)
async def public_write_cell(
    data: CellWrite,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:cells")),
):
    """Write (upsert) a single cell value using an API key with write:cells scope."""
    return await write_cell(
        db,
        line_item_id=data.line_item_id,
        dimension_members=data.dimension_members,
        version_id=data.version_id,
        value=data.value,
    )


@router.post(
    "/cells/bulk",
    response_model=List[CellRead],
    status_code=status.HTTP_200_OK,
    summary="Bulk write cells (API key: write:cells)",
)
async def public_write_cells_bulk(
    data: CellBulkWrite,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:cells")),
):
    """Bulk write (upsert) multiple cell values using an API key with write:cells scope."""
    return await write_cells_bulk(db, cells=data.cells)


# ── Import/Export ─────────────────────────────────────────────────────────────

@router.post(
    "/dimensions/{dimension_id}/import",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import dimension items (API key: write:models)",
)
async def public_import_dimension_items(
    dimension_id: uuid.UUID,
    file: UploadFile = File(...),
    name_column: str = Query("name", description="Column that contains item names"),
    parent_column: Optional[str] = Query(None, description="Column that contains parent item names"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    del api_key
    result = await db.execute(select(Dimension).where(Dimension.id == dimension_id))
    dimension = result.scalar_one_or_none()
    if dimension is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dimension not found")

    rows = await _parse_upload_file(file)
    if len(rows) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File contains no data rows",
        )

    if name_column not in rows[0]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Column '%s' not found in file. Available columns: %s"
            % (name_column, list(rows[0].keys())),
        )

    return await import_to_dimension(
        db=db,
        dimension_id=dimension_id,
        rows=rows,
        name_column=name_column,
        parent_column=parent_column,
    )


@router.post(
    "/modules/{module_id}/import",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import module cells (API key: write:models)",
)
async def public_import_module_cells(
    module_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    del api_key
    mod_result = await db.execute(select(Module).where(Module.id == module_id))
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    rows = await _parse_upload_file(file)
    if len(rows) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File contains no data rows",
        )

    li_result = await db.execute(select(LineItem).where(LineItem.module_id == module_id))
    line_items = list(li_result.scalars().all())
    li_by_name: Dict[str, uuid.UUID] = {li.name: li.id for li in line_items}

    columns = list(rows[0].keys())
    line_item_mapping: Dict[str, uuid.UUID] = {}
    for col in columns[1:]:
        if col in li_by_name:
            line_item_mapping[col] = li_by_name[col]

    if len(line_item_mapping) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No columns match any line item in this module. "
                "Module line items: %s. File columns: %s" % (list(li_by_name.keys()), columns)
            ),
        )

    return await import_to_module(
        db=db,
        module_id=module_id,
        rows=rows,
        line_item_mapping=line_item_mapping,
        dimension_mapping={},
    )


@router.get(
    "/modules/{module_id}/export",
    summary="Export module data (API key: read:models)",
)
async def public_export_module(
    module_id: uuid.UUID,
    format: ExportFormat = Query(ExportFormat.csv, description="Export format: csv or xlsx"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    del api_key
    mod_result = await db.execute(select(Module).where(Module.id == module_id))
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    if format == ExportFormat.xlsx:
        content = await export_module_to_excel(db, module_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "%s.xlsx" % module.name
    else:
        content = await export_module_to_csv(db, module_id)
        media_type = "text/csv"
        filename = "%s.csv" % module.name

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": 'attachment; filename="%s"' % filename},
    )


# ── Processes/Pipelines ───────────────────────────────────────────────────────

@router.post(
    "/processes/{process_id}/run",
    response_model=ProcessRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a process (API key: write:models)",
)
async def public_run_process(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    process = await get_process_by_id(db, process_id)
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process not found")
    return await run_process(db, process_id=process_id, user_id=api_key.user_id)


@router.get(
    "/processes/{process_id}/runs",
    response_model=List[ProcessRunResponse],
    summary="List process runs (API key: read:models)",
)
async def public_list_process_runs(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    del api_key
    process = await get_process_by_id(db, process_id)
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Process not found")
    return await get_process_runs(db, process_id=process_id)


@router.post(
    "/pipelines/{pipeline_id}/trigger",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a pipeline run (API key: write:models)",
)
async def public_trigger_pipeline_run(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    try:
        run = await trigger_pipeline_run(db, pipeline, api_key.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PipelineRunResponse.model_validate(run)


@router.post(
    "/pipeline-runs/{run_id}/execute",
    response_model=PipelineRunResponse,
    summary="Execute a pipeline run (API key: write:models)",
)
async def public_execute_pipeline_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    del api_key
    run = await get_run_by_id(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    try:
        updated = await execute_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PipelineRunResponse.model_validate(updated)


@router.get(
    "/pipeline-runs/{run_id}",
    response_model=PipelineRunDetail,
    summary="Get pipeline run details (API key: read:models)",
)
async def public_get_pipeline_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("read:models")),
):
    del api_key
    run = await get_run_by_id(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    detail = PipelineRunDetail.model_validate(run)
    detail.step_logs = [PipelineStepLogResponse.model_validate(step_log) for step_log in run.step_logs]
    return detail


@router.post(
    "/pipelines/{pipeline_id}/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger and execute a pipeline (API key: write:models)",
)
async def public_run_pipeline(
    pipeline_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_scope("write:models")),
):
    pipeline = await get_pipeline_by_id(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    try:
        run = await trigger_pipeline_run(db, pipeline, api_key.user_id)
        updated = await execute_run(db, run)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PipelineRunResponse.model_validate(updated)
