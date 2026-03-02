import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.data_hub import (
    DataHubImportRequest,
    DataHubImportResponse,
    DataHubLineageResponse,
    DataHubPublishRequest,
    DataHubPublishResponse,
    DataHubRowsListResponse,
    DataHubRowsWriteRequest,
    DataHubTableCreate,
    DataHubTableResponse,
    DataHubTableUpdate,
    DataHubTransformRequest,
    DataHubTransformResponse,
)
from app.services.data_hub import (
    DataHubValidationError,
    append_table_rows,
    create_table,
    delete_table,
    get_table_by_id,
    import_table_rows_from_connector,
    list_lineages_for_table,
    list_rows_for_table,
    list_tables_for_model,
    publish_table_to_module,
    replace_table_rows,
    transform_table_rows,
    update_table,
)
from app.services.planning_model import get_model_by_id

router = APIRouter(tags=["data-hub"])


def _raise_404(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def _get_model_or_404(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = await get_model_by_id(db, model_id)
    if model is None:
        _raise_404("Model not found")
    return model


async def _get_table_or_404(
    table_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    table = await get_table_by_id(db, table_id)
    if table is None:
        _raise_404("Data hub table not found")
    return table


@router.post(
    "/models/{model_id}/data-hub/tables",
    response_model=DataHubTableResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_hub_table_endpoint(
    model_id: uuid.UUID,
    data: DataHubTableCreate,
    _model=Depends(_get_model_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await create_table(
            db,
            model_id=model_id,
            user_id=current_user.id,
            data=data,
        )
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data hub table name already exists for this model",
        ) from exc


@router.get(
    "/models/{model_id}/data-hub/tables",
    response_model=List[DataHubTableResponse],
)
async def list_data_hub_tables_endpoint(
    model_id: uuid.UUID,
    _model=Depends(_get_model_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_tables_for_model(db, model_id=model_id)


@router.get(
    "/data-hub/tables/{table_id}",
    response_model=DataHubTableResponse,
)
async def get_data_hub_table_endpoint(
    table=Depends(_get_table_or_404),
):
    return table


@router.patch(
    "/data-hub/tables/{table_id}",
    response_model=DataHubTableResponse,
)
async def update_data_hub_table_endpoint(
    data: DataHubTableUpdate,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_table(db, table=table, data=data)
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Data hub table name already exists for this model",
        ) from exc


@router.delete(
    "/data-hub/tables/{table_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_data_hub_table_endpoint(
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    await delete_table(db, table=table)


@router.get(
    "/data-hub/tables/{table_id}/rows",
    response_model=DataHubRowsListResponse,
)
async def list_data_hub_rows_endpoint(
    table=Depends(_get_table_or_404),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    total_count, rows = await list_rows_for_table(
        db,
        table_id=table.id,
        offset=offset,
        limit=limit,
    )
    return DataHubRowsListResponse(total_count=total_count, rows=rows)


@router.put(
    "/data-hub/tables/{table_id}/rows",
    response_model=DataHubTableResponse,
)
async def replace_data_hub_rows_endpoint(
    data: DataHubRowsWriteRequest,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await replace_table_rows(db, table=table, data=data)
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/data-hub/tables/{table_id}/rows/append",
    response_model=DataHubTableResponse,
)
async def append_data_hub_rows_endpoint(
    data: DataHubRowsWriteRequest,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await append_table_rows(db, table=table, data=data)
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/data-hub/tables/{table_id}/import",
    response_model=DataHubImportResponse,
)
async def import_data_hub_rows_endpoint(
    data: DataHubImportRequest,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated_table, rows_imported = await import_table_rows_from_connector(
            db,
            table=table,
            data=data,
        )
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return DataHubImportResponse(table=updated_table, rows_imported=rows_imported)


@router.post(
    "/data-hub/tables/{table_id}/transform",
    response_model=DataHubTransformResponse,
)
async def transform_data_hub_rows_endpoint(
    data: DataHubTransformRequest,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        updated_table, rows_before, rows_after = await transform_table_rows(
            db,
            table=table,
            data=data,
        )
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return DataHubTransformResponse(
        table=updated_table,
        rows_before=rows_before,
        rows_after=rows_after,
    )


@router.post(
    "/data-hub/tables/{table_id}/publish",
    response_model=DataHubPublishResponse,
)
async def publish_data_hub_table_endpoint(
    data: DataHubPublishRequest,
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    try:
        lineage, rows_processed, cells_written = await publish_table_to_module(
            db,
            table=table,
            data=data,
        )
    except DataHubValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return DataHubPublishResponse(
        table_id=table.id,
        lineage_id=lineage.id,
        target_model_id=lineage.target_model_id,
        target_module_id=lineage.target_module_id,
        rows_processed=rows_processed,
        cells_written=cells_written,
        last_published_at=lineage.last_published_at,
    )


@router.get(
    "/data-hub/tables/{table_id}/lineage",
    response_model=List[DataHubLineageResponse],
)
async def list_data_hub_lineage_endpoint(
    table=Depends(_get_table_or_404),
    db: AsyncSession = Depends(get_db),
):
    return await list_lineages_for_table(db, table_id=table.id)
