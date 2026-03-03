from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.module import Module
    from app.models.planning_model import PlanningModel
    from app.models.user import User


class DataHubColumnType(str, enum.Enum):
    text = "text"
    integer = "integer"
    number = "number"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"


class DataHubTable(Base):
    __tablename__ = "data_hub_tables"
    __table_args__ = (
        UniqueConstraint("model_id", "name", name="uq_data_hub_tables_model_name"),
        Index("ix_data_hub_tables_model_id", "model_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_definition: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    model: Mapped["PlanningModel"] = relationship("PlanningModel", lazy="selectin")  # noqa: F821
    creator: Mapped[Optional["User"]] = relationship("User", lazy="selectin")  # noqa: F821
    rows: Mapped[List["DataHubRow"]] = relationship(
        "DataHubRow",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DataHubRow.sort_order",
    )
    lineages: Mapped[List["DataHubLineage"]] = relationship(
        "DataHubLineage",
        back_populates="table",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DataHubLineage.updated_at.desc()",
    )


class DataHubRow(Base):
    __tablename__ = "data_hub_rows"
    __table_args__ = (
        UniqueConstraint("table_id", "sort_order", name="uq_data_hub_rows_table_sort_order"),
        Index("ix_data_hub_rows_table_id", "table_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("data_hub_tables.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    table: Mapped["DataHubTable"] = relationship(
        "DataHubTable", back_populates="rows", lazy="selectin"
    )


class DataHubLineage(Base):
    __tablename__ = "data_hub_lineages"
    __table_args__ = (
        UniqueConstraint(
            "table_id",
            "target_module_id",
            name="uq_data_hub_lineages_table_module",
        ),
        Index("ix_data_hub_lineages_table_id", "table_id"),
        Index("ix_data_hub_lineages_target_model_id", "target_model_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("data_hub_tables.id", ondelete="CASCADE"), nullable=False
    )
    target_model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("planning_models.id", ondelete="CASCADE"), nullable=False
    )
    target_module_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="SET NULL"), nullable=True
    )
    mapping_config: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    records_published: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    table: Mapped["DataHubTable"] = relationship(
        "DataHubTable", back_populates="lineages", lazy="selectin"
    )
    target_model: Mapped["PlanningModel"] = relationship(
        "PlanningModel", lazy="selectin"
    )  # noqa: F821
    target_module: Mapped[Optional["Module"]] = relationship(
        "Module", lazy="selectin"
    )  # noqa: F821
