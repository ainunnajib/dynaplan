"""
Import/export API endpoints for dimensions and modules.
"""
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.dimension import Dimension
from app.models.module import LineItem, Module
from app.models.user import User
from app.schemas.import_export import ExportFormat, ImportPreview, ImportResult
from app.services.import_export import (
    build_import_preview,
    export_module_to_csv,
    export_module_to_excel,
    import_to_dimension,
    import_to_module,
    parse_csv,
    parse_excel,
)

router = APIRouter(tags=["import-export"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_format(filename: Optional[str], content_type: Optional[str]) -> str:
    """Return 'csv' or 'xlsx' based on filename/content_type."""
    if filename:
        lower = filename.lower()
        if lower.endswith(".xlsx") or lower.endswith(".xls"):
            return "xlsx"
        if lower.endswith(".csv"):
            return "csv"
    if content_type and "spreadsheet" in content_type:
        return "xlsx"
    return "csv"


async def _parse_file(file: UploadFile):
    """Read and parse an uploaded CSV or Excel file. Returns (rows, fmt)."""
    content = await file.read()
    fmt = _detect_format(file.filename, file.content_type)
    if fmt == "xlsx":
        try:
            rows = parse_excel(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to parse Excel file: {exc}",
            )
    else:
        try:
            rows = parse_csv(content)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to parse CSV file: {exc}",
            )
    return rows, fmt


# ── Dimension import ───────────────────────────────────────────────────────────

@router.post(
    "/dimensions/{dimension_id}/import",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import dimension items from CSV or Excel",
)
async def import_dimension_items(
    dimension_id: uuid.UUID,
    file: UploadFile = File(...),
    name_column: str = Query("name", description="Column that contains item names"),
    parent_column: Optional[str] = Query(None, description="Column that contains parent item names"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a CSV or Excel file to import items into a dimension."""
    # Verify dimension exists
    result = await db.execute(select(Dimension).where(Dimension.id == dimension_id))
    dimension = result.scalar_one_or_none()
    if dimension is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dimension not found",
        )

    rows, _fmt = await _parse_file(file)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File contains no data rows",
        )

    if name_column not in rows[0]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Column '{name_column}' not found in file. Available columns: {list(rows[0].keys())}",
        )

    return await import_to_dimension(
        db=db,
        dimension_id=dimension_id,
        rows=rows,
        name_column=name_column,
        parent_column=parent_column,
    )


# ── Module cell import ─────────────────────────────────────────────────────────

@router.post(
    "/modules/{module_id}/import",
    response_model=ImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import cell data from CSV or Excel into a module",
)
async def import_module_cells(
    module_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV or Excel file to import cell values into a module.

    The file must have columns matching line item names. The first column is
    treated as the dimension key (row label). A mapping of all line item
    columns -> LineItem UUIDs is built automatically.
    """
    # Verify module exists
    mod_result = await db.execute(select(Module).where(Module.id == module_id))
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )

    rows, _fmt = await _parse_file(file)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File contains no data rows",
        )

    # Load line items for this module
    li_result = await db.execute(
        select(LineItem).where(LineItem.module_id == module_id)
    )
    line_items = list(li_result.scalars().all())
    li_by_name: Dict[str, uuid.UUID] = {li.name: li.id for li in line_items}

    columns = list(rows[0].keys())

    # Build line_item_mapping: CSV column -> LineItem UUID (skip first col = dimension key)
    line_item_mapping: Dict[str, uuid.UUID] = {}
    for col in columns[1:]:
        if col in li_by_name:
            line_item_mapping[col] = li_by_name[col]

    if not line_item_mapping:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No columns match any line item in this module. "
                f"Module line items: {list(li_by_name.keys())}. "
                f"File columns: {columns}"
            ),
        )

    # dimension_mapping is empty — cells are stored with an empty dimension key
    # (single-dimension case). Callers who need specific dimension members should
    # use the service directly.
    dimension_mapping: Dict[str, uuid.UUID] = {}

    return await import_to_module(
        db=db,
        module_id=module_id,
        rows=rows,
        line_item_mapping=line_item_mapping,
        dimension_mapping=dimension_mapping,
    )


# ── Module export ──────────────────────────────────────────────────────────────

@router.get(
    "/modules/{module_id}/export",
    summary="Export module data as CSV or Excel",
)
async def export_module(
    module_id: uuid.UUID,
    format: ExportFormat = Query(ExportFormat.csv, description="Export format: csv or xlsx"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all cell data from a module as CSV or Excel."""
    mod_result = await db.execute(select(Module).where(Module.id == module_id))
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )

    if format == ExportFormat.xlsx:
        content = await export_module_to_excel(db, module_id)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"{module.name}.xlsx"
    else:
        content = await export_module_to_csv(db, module_id)
        media_type = "text/csv"
        filename = f"{module.name}.csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Import preview ─────────────────────────────────────────────────────────────

@router.post(
    "/modules/{module_id}/import/preview",
    response_model=ImportPreview,
    status_code=status.HTTP_200_OK,
    summary="Preview import mapping before committing",
)
async def preview_module_import(
    module_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parse an uploaded file and return a preview of columns and sample rows.
    The suggested_mapping in the response will have all columns set to None;
    the client is expected to populate the mapping and then call the import endpoint.
    """
    mod_result = await db.execute(select(Module).where(Module.id == module_id))
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Module not found",
        )

    rows, _fmt = await _parse_file(file)
    preview_data = build_import_preview(rows, max_sample=5)

    return ImportPreview(
        column_names=preview_data["column_names"],
        sample_rows=preview_data["sample_rows"],
        suggested_mapping=preview_data["suggested_mapping"],
    )
