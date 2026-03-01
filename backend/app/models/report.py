import enum
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PageSize(str, enum.Enum):
    a4 = "a4"
    letter = "letter"
    custom = "custom"


class Orientation(str, enum.Enum):
    portrait = "portrait"
    landscape = "landscape"


class SectionType(str, enum.Enum):
    narrative = "narrative"
    grid = "grid"
    chart = "chart"
    kpi_row = "kpi_row"
    page_break = "page_break"
    spacer = "spacer"


class ExportFormat(str, enum.Enum):
    pdf = "pdf"
    xlsx = "xlsx"
    pptx = "pptx"


class ExportStatus(str, enum.Enum):
    pending = "pending"
    generating = "generating"
    complete = "complete"
    failed = "failed"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_size: Mapped[PageSize] = mapped_column(
        Enum(PageSize), nullable=False, default=PageSize.a4
    )
    orientation: Mapped[Orientation] = mapped_column(
        Enum(Orientation), nullable=False, default=Orientation.portrait
    )
    margin_top: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    margin_right: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    margin_bottom: Mapped[float] = mapped_column(Float, nullable=False, default=20.0)
    margin_left: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    header_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footer_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sections: Mapped[List["ReportSection"]] = relationship(
        "ReportSection",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ReportSection.sort_order",
    )
    exports: Mapped[List["ReportExport"]] = relationship(
        "ReportExport",
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ReportExport.created_at.desc()",
    )


class ReportSection(Base):
    __tablename__ = "report_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    section_type: Mapped[SectionType] = mapped_column(
        Enum(SectionType), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    height_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    report: Mapped["Report"] = relationship("Report", back_populates="sections")


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    exported_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat), nullable=False
    )
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus), nullable=False, default=ExportStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped["Report"] = relationship("Report", back_populates="exports")
