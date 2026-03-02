import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.data_hub import DataHubColumnType


class DataHubColumnSchema(BaseModel):
    name: str
    data_type: DataHubColumnType
    nullable: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) == 0:
            raise ValueError("Column name is required")
        return normalized


class DataHubTableCreate(BaseModel):
    name: str
    description: Optional[str] = None
    schema_definition: List[DataHubColumnSchema] = Field(default_factory=list)


class DataHubTableUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schema_definition: Optional[List[DataHubColumnSchema]] = None


class DataHubRowsWriteRequest(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    infer_schema: bool = False


class DataHubRowResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    sort_order: int
    row_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataHubRowsListResponse(BaseModel):
    total_count: int
    rows: List[DataHubRowResponse]


class DataHubImportRequest(BaseModel):
    connection_id: Optional[uuid.UUID] = None
    connector_type: Optional[str] = None
    connector_config: Optional[Dict[str, Any]] = None
    replace_existing: bool = True
    infer_schema: bool = True

    @model_validator(mode="after")
    def validate_connector_source(self):
        if self.connection_id is None and self.connector_type is None:
            raise ValueError("Either connection_id or connector_type is required")
        return self


class DataHubTransformOperation(BaseModel):
    operation_type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None

    @field_validator("operation_type")
    @classmethod
    def validate_operation_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        supported = {"transform", "filter", "map", "aggregate"}
        if normalized not in supported:
            raise ValueError(
                "operation_type must be one of: %s"
                % ", ".join(sorted(supported))
            )
        return normalized


class DataHubTransformRequest(BaseModel):
    operations: List[DataHubTransformOperation]
    replace_existing: bool = True

    @field_validator("operations")
    @classmethod
    def validate_operations(cls, value: List[DataHubTransformOperation]) -> List[DataHubTransformOperation]:
        if len(value) == 0:
            raise ValueError("At least one transform operation is required")
        return value


class DataHubPublishRequest(BaseModel):
    module_id: uuid.UUID
    line_item_map: Dict[str, uuid.UUID]
    dimension_columns: List[str] = Field(default_factory=list)
    dimension_member_map: Dict[str, Dict[str, uuid.UUID]] = Field(default_factory=dict)
    static_dimension_members: List[uuid.UUID] = Field(default_factory=list)
    version_id: Optional[uuid.UUID] = None
    allow_null_values: bool = False
    batch_size: int = 500

    @field_validator("line_item_map")
    @classmethod
    def validate_line_item_map(cls, value: Dict[str, uuid.UUID]) -> Dict[str, uuid.UUID]:
        if len(value) == 0:
            raise ValueError("line_item_map cannot be empty")
        return value

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("batch_size must be greater than 0")
        return value


class DataHubLineageResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    target_model_id: uuid.UUID
    target_module_id: Optional[uuid.UUID]
    mapping_config: Dict[str, Any]
    records_published: int
    last_published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataHubTableResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    name: str
    description: Optional[str]
    schema_definition: List[DataHubColumnSchema]
    row_count: int
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataHubImportResponse(BaseModel):
    table: DataHubTableResponse
    rows_imported: int


class DataHubTransformResponse(BaseModel):
    table: DataHubTableResponse
    rows_before: int
    rows_after: int


class DataHubPublishResponse(BaseModel):
    table_id: uuid.UUID
    lineage_id: uuid.UUID
    target_model_id: uuid.UUID
    target_module_id: Optional[uuid.UUID]
    rows_processed: int
    cells_written: int
    last_published_at: Optional[datetime]
