import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.models.report import (
    ExportFormat,
    ExportStatus,
    Orientation,
    PageSize,
    SectionType,
)


# ── Report schemas ───────────────────────────────────────────────────────────

class ReportCreate(BaseModel):
    name: str
    description: Optional[str] = None
    page_size: PageSize = PageSize.a4
    orientation: Orientation = Orientation.portrait
    margin_top: float = 20.0
    margin_right: float = 15.0
    margin_bottom: float = 20.0
    margin_left: float = 15.0
    header_html: Optional[str] = None
    footer_html: Optional[str] = None


class ReportUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    page_size: Optional[PageSize] = None
    orientation: Optional[Orientation] = None
    margin_top: Optional[float] = None
    margin_right: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    header_html: Optional[str] = None
    footer_html: Optional[str] = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: Optional[str]
    page_size: PageSize
    orientation: Orientation
    margin_top: float
    margin_right: float
    margin_bottom: float
    margin_left: float
    header_html: Optional[str]
    footer_html: Optional[str]
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Section schemas ──────────────────────────────────────────────────────────

class ReportSectionCreate(BaseModel):
    section_type: SectionType
    title: Optional[str] = None
    content_config: Optional[Dict[str, Any]] = None
    sort_order: int = 0
    height_mm: Optional[float] = None


class ReportSectionUpdate(BaseModel):
    title: Optional[str] = None
    content_config: Optional[Dict[str, Any]] = None
    sort_order: Optional[int] = None
    height_mm: Optional[float] = None


class ReportSectionResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    section_type: SectionType
    title: Optional[str]
    content_config: Optional[Dict[str, Any]]
    sort_order: int
    height_mm: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Export schemas ───────────────────────────────────────────────────────────

class ReportExportCreate(BaseModel):
    format: ExportFormat


class ReportExportResponse(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    exported_by: uuid.UUID
    format: ExportFormat
    file_path: Optional[str]
    status: ExportStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Publish schema ───────────────────────────────────────────────────────────

class ReportPublishRequest(BaseModel):
    is_published: bool


# ── Reorder schema ───────────────────────────────────────────────────────────

class ReportSectionReorder(BaseModel):
    section_ids: List[uuid.UUID]


# ── Combined response ────────────────────────────────────────────────────────

class ReportWithSectionsResponse(ReportResponse):
    sections: List[ReportSectionResponse] = []
