import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.report import (
    ExportStatus,
    Report,
    ReportExport,
    ReportSection,
)
from app.schemas.report import (
    ReportCreate,
    ReportExportCreate,
    ReportSectionCreate,
    ReportSectionUpdate,
    ReportUpdate,
)


# ── Report CRUD ──────────────────────────────────────────────────────────────

async def create_report(
    db: AsyncSession,
    data: ReportCreate,
    model_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Report:
    report = Report(
        name=data.name,
        description=data.description,
        model_id=model_id,
        owner_id=owner_id,
        page_size=data.page_size,
        orientation=data.orientation,
        margin_top=data.margin_top,
        margin_right=data.margin_right,
        margin_bottom=data.margin_bottom,
        margin_left=data.margin_left,
        header_html=data.header_html,
        footer_html=data.footer_html,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def get_report_by_id(
    db: AsyncSession, report_id: uuid.UUID
) -> Optional[Report]:
    result = await db.execute(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.sections))
    )
    return result.scalar_one_or_none()


async def list_reports_for_model(
    db: AsyncSession, model_id: uuid.UUID, owner_id: uuid.UUID
) -> List[Report]:
    result = await db.execute(
        select(Report)
        .where(Report.model_id == model_id, Report.owner_id == owner_id)
        .order_by(Report.created_at)
    )
    return list(result.scalars().all())


async def update_report(
    db: AsyncSession, report: Report, data: ReportUpdate
) -> Report:
    for field in [
        "name", "description", "page_size", "orientation",
        "margin_top", "margin_right", "margin_bottom", "margin_left",
        "header_html", "footer_html",
    ]:
        value = getattr(data, field, None)
        if value is not None:
            setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return report


async def delete_report(db: AsyncSession, report: Report) -> None:
    await db.delete(report)
    await db.commit()


async def publish_report(
    db: AsyncSession, report: Report, is_published: bool
) -> Report:
    report.is_published = is_published
    await db.commit()
    await db.refresh(report)
    return report


# ── Section CRUD ─────────────────────────────────────────────────────────────

async def create_section(
    db: AsyncSession,
    data: ReportSectionCreate,
    report_id: uuid.UUID,
) -> ReportSection:
    section = ReportSection(
        report_id=report_id,
        section_type=data.section_type,
        title=data.title,
        content_config=data.content_config or {},
        sort_order=data.sort_order,
        height_mm=data.height_mm,
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


async def get_section_by_id(
    db: AsyncSession, section_id: uuid.UUID
) -> Optional[ReportSection]:
    result = await db.execute(
        select(ReportSection).where(ReportSection.id == section_id)
    )
    return result.scalar_one_or_none()


async def update_section(
    db: AsyncSession, section: ReportSection, data: ReportSectionUpdate
) -> ReportSection:
    if data.title is not None:
        section.title = data.title
    if data.content_config is not None:
        section.content_config = data.content_config
    if data.sort_order is not None:
        section.sort_order = data.sort_order
    if data.height_mm is not None:
        section.height_mm = data.height_mm
    await db.commit()
    await db.refresh(section)
    return section


async def delete_section(db: AsyncSession, section: ReportSection) -> None:
    await db.delete(section)
    await db.commit()


async def reorder_sections(
    db: AsyncSession,
    report_id: uuid.UUID,
    section_ids: List[uuid.UUID],
) -> List[ReportSection]:
    """Assign sort_order based on position in the provided section_ids list."""
    result = await db.execute(
        select(ReportSection).where(ReportSection.report_id == report_id)
    )
    sections = {s.id: s for s in result.scalars().all()}

    for order, sid in enumerate(section_ids):
        if sid in sections:
            sections[sid].sort_order = order

    await db.commit()
    updated = list(sections.values())
    for section in updated:
        await db.refresh(section)
    updated.sort(key=lambda s: s.sort_order)
    return updated


# ── Export lifecycle ─────────────────────────────────────────────────────────

async def initiate_export(
    db: AsyncSession,
    data: ReportExportCreate,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ReportExport:
    export = ReportExport(
        report_id=report_id,
        exported_by=user_id,
        format=data.format,
        status=ExportStatus.pending,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)
    return export


async def complete_export(
    db: AsyncSession, export: ReportExport, file_path: str
) -> ReportExport:
    export.status = ExportStatus.complete
    export.file_path = file_path
    await db.commit()
    await db.refresh(export)
    return export


async def fail_export(db: AsyncSession, export: ReportExport) -> ReportExport:
    export.status = ExportStatus.failed
    await db.commit()
    await db.refresh(export)
    return export


async def list_exports_for_report(
    db: AsyncSession, report_id: uuid.UUID
) -> List[ReportExport]:
    result = await db.execute(
        select(ReportExport)
        .where(ReportExport.report_id == report_id)
        .order_by(ReportExport.created_at.desc())
    )
    return list(result.scalars().all())
