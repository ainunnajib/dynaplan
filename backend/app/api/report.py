import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.report import (
    ReportCreate,
    ReportExportCreate,
    ReportExportResponse,
    ReportPublishRequest,
    ReportResponse,
    ReportSectionCreate,
    ReportSectionReorder,
    ReportSectionResponse,
    ReportSectionUpdate,
    ReportUpdate,
    ReportWithSectionsResponse,
)
from app.services.report import (
    create_report,
    create_section,
    delete_report,
    delete_section,
    get_report_by_id,
    get_section_by_id,
    initiate_export,
    list_exports_for_report,
    list_reports_for_model,
    publish_report,
    reorder_sections,
    update_report,
    update_section,
)

router = APIRouter(tags=["reports"])


# ── Dependency helpers ────────────────────────────────────────────────────────

async def _get_owned_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_by_id(db, report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    if report.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this report",
        )
    return report


async def _get_owned_section(
    section_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    section = await get_section_by_id(db, section_id)
    if section is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found",
        )
    report = await get_report_by_id(db, section.report_id)
    if report is None or report.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this section",
        )
    return section


# ── Report routes ─────────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report_route(
    model_id: uuid.UUID,
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await create_report(db, data, model_id=model_id, owner_id=current_user.id)
    return report


@router.get(
    "/models/{model_id}/reports",
    response_model=List[ReportResponse],
)
async def list_reports_route(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_reports_for_model(db, model_id=model_id, owner_id=current_user.id)


@router.get(
    "/reports/{report_id}",
    response_model=ReportWithSectionsResponse,
)
async def get_report_route(
    report=Depends(_get_owned_report),
):
    return report


@router.put(
    "/reports/{report_id}",
    response_model=ReportResponse,
)
async def update_report_route(
    data: ReportUpdate,
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    return await update_report(db, report, data)


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_report_route(
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    await delete_report(db, report)


# ── Section routes ────────────────────────────────────────────────────────────

@router.post(
    "/reports/{report_id}/sections",
    response_model=ReportSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_section_route(
    data: ReportSectionCreate,
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    section = await create_section(db, data, report_id=report.id)
    return section


@router.put(
    "/sections/{section_id}",
    response_model=ReportSectionResponse,
)
async def update_section_route(
    data: ReportSectionUpdate,
    section=Depends(_get_owned_section),
    db: AsyncSession = Depends(get_db),
):
    return await update_section(db, section, data)


@router.delete(
    "/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_section_route(
    section=Depends(_get_owned_section),
    db: AsyncSession = Depends(get_db),
):
    await delete_section(db, section)


@router.post(
    "/reports/{report_id}/sections/reorder",
    response_model=List[ReportSectionResponse],
)
async def reorder_sections_route(
    data: ReportSectionReorder,
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    return await reorder_sections(db, report_id=report.id, section_ids=data.section_ids)


# ── Export routes ─────────────────────────────────────────────────────────────

@router.post(
    "/reports/{report_id}/export",
    response_model=ReportExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_report_route(
    data: ReportExportCreate,
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await initiate_export(db, data, report_id=report.id, user_id=current_user.id)


@router.get(
    "/reports/{report_id}/exports",
    response_model=List[ReportExportResponse],
)
async def list_exports_route(
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    return await list_exports_for_report(db, report_id=report.id)


# ── Publish route ─────────────────────────────────────────────────────────────

@router.put(
    "/reports/{report_id}/publish",
    response_model=ReportResponse,
)
async def publish_report_route(
    data: ReportPublishRequest,
    report=Depends(_get_owned_report),
    db: AsyncSession = Depends(get_db),
):
    return await publish_report(db, report, is_published=data.is_published)
