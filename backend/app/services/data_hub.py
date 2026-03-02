import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.connectors import create_connector
from app.connectors.base import ConnectorError
from app.engine.pipeline_runtime.transforms import (
    apply_aggregate_step,
    apply_filter_step,
    apply_map_step,
    apply_transform_step,
)
from app.models.cloudworks import CloudWorksConnection
from app.models.data_hub import DataHubColumnType, DataHubLineage, DataHubRow, DataHubTable
from app.models.module import Module
from app.schemas.cell import CellWrite
from app.schemas.data_hub import (
    DataHubColumnSchema,
    DataHubImportRequest,
    DataHubPublishRequest,
    DataHubRowsWriteRequest,
    DataHubTableCreate,
    DataHubTableUpdate,
    DataHubTransformRequest,
)
from app.services.cell import write_cells_bulk


class DataHubValidationError(ValueError):
    """Raised when Data Hub table data is invalid."""


def _is_nullish(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:  # noqa: BLE001
        return value is None


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_scalar(value: Any) -> Any:
    if _is_nullish(value):
        return None

    if isinstance(value, pd.Timestamp):
        return _normalize_datetime(value.to_pydatetime()).isoformat()
    if isinstance(value, datetime):
        return _normalize_datetime(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):  # pragma: no cover
        return value

    # Handle NumPy scalar values without importing numpy directly.
    if hasattr(value, "item"):
        try:
            return _normalize_scalar(value.item())
        except Exception:  # noqa: BLE001
            pass

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return str(value)


def _coerce_boolean(value: Any, column_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value in (0, 0.0):
            return False
        if value in (1, 1.0):
            return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    raise DataHubValidationError(
        "Column '%s' expects boolean-compatible values" % column_name
    )


def _coerce_integer(value: Any, column_name: str) -> int:
    if isinstance(value, bool):
        raise DataHubValidationError(
            "Column '%s' expects integer values, received boolean" % column_name
        )
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise DataHubValidationError(
                "Column '%s' expects integer values, received %s"
                % (column_name, value)
            )
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            raise DataHubValidationError(
                "Column '%s' expects integer values, received empty string"
                % column_name
            )
        try:
            parsed = float(text)
        except ValueError as exc:
            raise DataHubValidationError(
                "Column '%s' expects integer values, received '%s'"
                % (column_name, value)
            ) from exc
        if not parsed.is_integer():
            raise DataHubValidationError(
                "Column '%s' expects integer values, received '%s'"
                % (column_name, value)
            )
        return int(parsed)
    raise DataHubValidationError(
        "Column '%s' expects integer values" % column_name
    )


def _coerce_number(value: Any, column_name: str) -> float:
    if isinstance(value, bool):
        raise DataHubValidationError(
            "Column '%s' expects numeric values, received boolean" % column_name
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            raise DataHubValidationError(
                "Column '%s' expects numeric values, received empty string"
                % column_name
            )
        try:
            return float(text)
        except ValueError as exc:
            raise DataHubValidationError(
                "Column '%s' expects numeric values, received '%s'"
                % (column_name, value)
            ) from exc
    raise DataHubValidationError(
        "Column '%s' expects numeric values" % column_name
    )


def _coerce_date(value: Any, column_name: str) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            raise DataHubValidationError(
                "Column '%s' expects date values, received empty string"
                % column_name
            )
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError as exc:
            raise DataHubValidationError(
                "Column '%s' expects ISO date values (YYYY-MM-DD)"
                % column_name
            ) from exc
    raise DataHubValidationError(
        "Column '%s' expects date values" % column_name
    )


def _coerce_datetime(value: Any, column_name: str) -> str:
    if isinstance(value, datetime):
        return _normalize_datetime(value).isoformat()
    if isinstance(value, date):
        dt_value = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        return dt_value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            raise DataHubValidationError(
                "Column '%s' expects datetime values, received empty string"
                % column_name
            )
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise DataHubValidationError(
                "Column '%s' expects ISO datetime values"
                % column_name
            ) from exc
        return _normalize_datetime(parsed).isoformat()
    raise DataHubValidationError(
        "Column '%s' expects datetime values" % column_name
    )


def _coerce_value_for_column(column: Dict[str, Any], value: Any) -> Any:
    column_name = str(column.get("name"))
    nullable = bool(column.get("nullable", True))
    if _is_nullish(value):
        if nullable:
            return None
        raise DataHubValidationError(
            "Column '%s' is required and does not allow null values"
            % column_name
        )

    raw_type = column.get("data_type", DataHubColumnType.text.value)
    data_type = DataHubColumnType(str(raw_type))

    if data_type == DataHubColumnType.text:
        return str(value)
    if data_type == DataHubColumnType.boolean:
        return _coerce_boolean(value, column_name)
    if data_type == DataHubColumnType.integer:
        return _coerce_integer(value, column_name)
    if data_type == DataHubColumnType.number:
        return _coerce_number(value, column_name)
    if data_type == DataHubColumnType.date:
        return _coerce_date(value, column_name)
    if data_type == DataHubColumnType.datetime:
        return _coerce_datetime(value, column_name)

    raise DataHubValidationError(
        "Column '%s' has unsupported type '%s'"
        % (column_name, data_type.value)
    )


def _normalize_schema_definition(
    schema_definition: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for entry in schema_definition:
        raw_name = str(entry.get("name", "")).strip()
        if len(raw_name) == 0:
            raise DataHubValidationError("Schema column name is required")
        if raw_name in seen:
            raise DataHubValidationError(
                "Schema contains duplicate column '%s'" % raw_name
            )
        seen.add(raw_name)

        raw_data_type = str(
            entry.get("data_type", DataHubColumnType.text.value)
        ).strip().lower()
        try:
            data_type = DataHubColumnType(raw_data_type)
        except ValueError as exc:
            raise DataHubValidationError(
                "Unsupported data type '%s' for column '%s'"
                % (raw_data_type, raw_name)
            ) from exc

        normalized.append(
            {
                "name": raw_name,
                "data_type": data_type.value,
                "nullable": bool(entry.get("nullable", True)),
            }
        )
    return normalized


def _build_schema_definition_from_columns(
    columns: List[DataHubColumnSchema],
) -> List[Dict[str, Any]]:
    return _normalize_schema_definition(
        [column.model_dump(mode="json") for column in columns]
    )


def _looks_like_integer(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            return False
        try:
            parsed = float(text)
        except ValueError:
            return False
        return parsed.is_integer()
    return False


def _looks_like_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            return False
        try:
            float(text)
            return True
        except ValueError:
            return False
    return False


def _looks_like_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "false", "t", "f", "yes", "no", "1", "0"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value in (0, 1, 0.0, 1.0)
    return False


def _looks_like_date(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if isinstance(value, date):
        return True
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            return False
        try:
            date.fromisoformat(text)
            return True
        except ValueError:
            return False
    return False


def _looks_like_datetime(value: Any) -> bool:
    if isinstance(value, datetime):
        return True
    if isinstance(value, str):
        text = value.strip()
        if len(text) == 0:
            return False
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            datetime.fromisoformat(normalized)
            return True
        except ValueError:
            return False
    return False


def _infer_column_type(values: List[Any]) -> DataHubColumnType:
    if len(values) == 0:
        return DataHubColumnType.text

    if all(_looks_like_boolean(value) for value in values):
        return DataHubColumnType.boolean
    if all(_looks_like_integer(value) for value in values):
        return DataHubColumnType.integer
    if all(_looks_like_number(value) for value in values):
        return DataHubColumnType.number
    if all(_looks_like_datetime(value) for value in values):
        return DataHubColumnType.datetime
    if all(_looks_like_date(value) for value in values):
        return DataHubColumnType.date
    return DataHubColumnType.text


def _infer_schema_definition_from_records(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    column_order: List[str] = []
    for row in rows:
        for column_name in row.keys():
            normalized_name = str(column_name)
            if normalized_name not in column_order:
                column_order.append(normalized_name)

    inferred: List[Dict[str, Any]] = []
    for column_name in column_order:
        all_values = [row.get(column_name) for row in rows]
        non_null_values = [value for value in all_values if not _is_nullish(value)]
        column_type = _infer_column_type(non_null_values)
        nullable = any(_is_nullish(value) for value in all_values)
        inferred.append(
            {
                "name": column_name,
                "data_type": column_type.value,
                "nullable": nullable,
            }
        )
    return inferred


def _infer_schema_definition_from_frame(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    records = _frame_to_records(frame)
    if len(records) > 0:
        return _infer_schema_definition_from_records(records)

    inferred: List[Dict[str, Any]] = []
    for column_name in frame.columns:
        dtype = str(frame[column_name].dtype).lower()
        if "bool" in dtype:
            data_type = DataHubColumnType.boolean
        elif "int" in dtype:
            data_type = DataHubColumnType.integer
        elif "float" in dtype:
            data_type = DataHubColumnType.number
        elif "datetime" in dtype:
            data_type = DataHubColumnType.datetime
        else:
            data_type = DataHubColumnType.text
        inferred.append(
            {
                "name": str(column_name),
                "data_type": data_type.value,
                "nullable": True,
            }
        )
    return inferred


def _normalize_rows_against_schema(
    rows: List[Dict[str, Any]],
    schema_definition: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized_schema = _normalize_schema_definition(schema_definition)
    allowed_columns = {entry["name"] for entry in normalized_schema}

    normalized_rows: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DataHubValidationError(
                "Row %s must be an object with column/value pairs"
                % index
            )

        unknown_columns = [
            str(column_name)
            for column_name in row.keys()
            if str(column_name) not in allowed_columns
        ]
        if len(unknown_columns) > 0:
            raise DataHubValidationError(
                "Row %s includes unknown columns: %s"
                % (index, ", ".join(sorted(unknown_columns)))
            )

        normalized_row: Dict[str, Any] = {}
        for column in normalized_schema:
            column_name = column["name"]
            raw_value = row.get(column_name)
            normalized_row[column_name] = _coerce_value_for_column(column, raw_value)
        normalized_rows.append(normalized_row)
    return normalized_rows


def _frame_to_records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if len(frame.index) == 0:
        return []

    sanitized = frame.where(pd.notna(frame), None)
    raw_records = sanitized.to_dict(orient="records")
    normalized_records: List[Dict[str, Any]] = []
    for row in raw_records:
        normalized_row: Dict[str, Any] = {}
        for column_name, value in row.items():
            normalized_row[str(column_name)] = _normalize_scalar(value)
        normalized_records.append(normalized_row)
    return normalized_records


def _chunk_cells(cells: List[CellWrite], batch_size: int) -> Iterable[List[CellWrite]]:
    for index in range(0, len(cells), batch_size):
        yield cells[index: index + batch_size]


def _serialize_publish_mapping(data: DataHubPublishRequest) -> Dict[str, Any]:
    return {
        "line_item_map": {
            column: str(line_item_id)
            for column, line_item_id in data.line_item_map.items()
        },
        "dimension_columns": list(data.dimension_columns),
        "dimension_member_map": {
            column: {
                source_key: str(member_id)
                for source_key, member_id in mapping.items()
            }
            for column, mapping in data.dimension_member_map.items()
        },
        "static_dimension_members": [
            str(member_id) for member_id in data.static_dimension_members
        ],
        "version_id": str(data.version_id) if data.version_id is not None else None,
        "allow_null_values": bool(data.allow_null_values),
        "batch_size": int(data.batch_size),
    }


def _parse_uuid_value(value: Any, field_name: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if value is None:
        raise DataHubValidationError("Field '%s' cannot be null" % field_name)
    text = str(value).strip()
    if len(text) == 0:
        raise DataHubValidationError("Field '%s' cannot be empty" % field_name)
    try:
        return uuid.UUID(text)
    except ValueError as exc:
        raise DataHubValidationError(
            "Field '%s' must be a UUID value" % field_name
        ) from exc


async def get_table_by_id(
    db: AsyncSession,
    table_id: uuid.UUID,
) -> Optional[DataHubTable]:
    result = await db.execute(
        select(DataHubTable)
        .where(DataHubTable.id == table_id)
        .options(
            selectinload(DataHubTable.lineages),
        )
    )
    return result.scalar_one_or_none()


async def _get_table_with_rows_by_id(
    db: AsyncSession,
    table_id: uuid.UUID,
) -> Optional[DataHubTable]:
    result = await db.execute(
        select(DataHubTable)
        .where(DataHubTable.id == table_id)
        .options(
            selectinload(DataHubTable.rows),
            selectinload(DataHubTable.lineages),
        )
    )
    return result.scalar_one_or_none()


async def list_tables_for_model(
    db: AsyncSession,
    model_id: uuid.UUID,
) -> List[DataHubTable]:
    result = await db.execute(
        select(DataHubTable)
        .where(DataHubTable.model_id == model_id)
        .options(selectinload(DataHubTable.lineages))
        .order_by(DataHubTable.created_at.asc())
    )
    return list(result.scalars().all())


async def create_table(
    db: AsyncSession,
    model_id: uuid.UUID,
    user_id: uuid.UUID,
    data: DataHubTableCreate,
) -> DataHubTable:
    name = data.name.strip()
    if len(name) == 0:
        raise DataHubValidationError("Table name is required")

    schema_definition = _build_schema_definition_from_columns(data.schema_definition)
    table = DataHubTable(
        model_id=model_id,
        created_by=user_id,
        name=name,
        description=data.description,
        schema_definition=schema_definition,
        row_count=0,
    )
    db.add(table)
    await db.commit()
    created = await get_table_by_id(db, table.id)
    return created if created is not None else table


async def update_table(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubTableUpdate,
) -> DataHubTable:
    if "name" in data.model_fields_set and data.name is not None:
        name = data.name.strip()
        if len(name) == 0:
            raise DataHubValidationError("Table name is required")
        table.name = name

    if "description" in data.model_fields_set:
        table.description = data.description

    if "schema_definition" in data.model_fields_set and data.schema_definition is not None:
        updated_schema = _build_schema_definition_from_columns(data.schema_definition)
        table_with_rows = await _get_table_with_rows_by_id(db, table.id)
        if table_with_rows is not None and len(table_with_rows.rows) > 0:
            normalized_rows = _normalize_rows_against_schema(
                [row.row_data for row in table_with_rows.rows],
                updated_schema,
            )
            for row, normalized_row in zip(table_with_rows.rows, normalized_rows):
                row.row_data = normalized_row
                db.add(row)
        table.schema_definition = updated_schema

    db.add(table)
    await db.commit()
    updated = await get_table_by_id(db, table.id)
    return updated if updated is not None else table


async def delete_table(
    db: AsyncSession,
    table: DataHubTable,
) -> None:
    await db.delete(table)
    await db.commit()


async def list_rows_for_table(
    db: AsyncSession,
    table_id: uuid.UUID,
    offset: int = 0,
    limit: int = 200,
) -> Tuple[int, List[DataHubRow]]:
    total_result = await db.execute(
        select(func.count())
        .select_from(DataHubRow)
        .where(DataHubRow.table_id == table_id)
    )
    total_count = int(total_result.scalar_one() or 0)

    rows_result = await db.execute(
        select(DataHubRow)
        .where(DataHubRow.table_id == table_id)
        .order_by(DataHubRow.sort_order.asc())
        .offset(max(offset, 0))
        .limit(max(limit, 1))
    )
    return total_count, list(rows_result.scalars().all())


async def _replace_rows(
    db: AsyncSession,
    table: DataHubTable,
    normalized_rows: List[Dict[str, Any]],
) -> DataHubTable:
    await db.execute(delete(DataHubRow).where(DataHubRow.table_id == table.id))

    for index, row_data in enumerate(normalized_rows):
        db.add(
            DataHubRow(
                table_id=table.id,
                sort_order=index,
                row_data=row_data,
            )
        )

    table.row_count = len(normalized_rows)
    await db.commit()
    updated = await get_table_by_id(db, table.id)
    return updated if updated is not None else table


async def _append_rows(
    db: AsyncSession,
    table: DataHubTable,
    normalized_rows: List[Dict[str, Any]],
) -> DataHubTable:
    start_index = int(table.row_count or 0)
    for offset, row_data in enumerate(normalized_rows):
        db.add(
            DataHubRow(
                table_id=table.id,
                sort_order=start_index + offset,
                row_data=row_data,
            )
        )

    table.row_count = start_index + len(normalized_rows)
    await db.commit()
    updated = await get_table_by_id(db, table.id)
    return updated if updated is not None else table


async def replace_table_rows(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubRowsWriteRequest,
) -> DataHubTable:
    raw_rows = list(data.rows or [])
    schema_definition = list(table.schema_definition or [])

    if len(schema_definition) == 0:
        if len(raw_rows) > 0 and not data.infer_schema:
            raise DataHubValidationError(
                "Table schema is empty; set infer_schema=true or define schema_definition first"
            )
        schema_definition = _infer_schema_definition_from_records(raw_rows)
        table.schema_definition = schema_definition

    normalized_rows = _normalize_rows_against_schema(raw_rows, schema_definition)
    return await _replace_rows(db, table, normalized_rows)


async def append_table_rows(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubRowsWriteRequest,
) -> DataHubTable:
    raw_rows = list(data.rows or [])
    if len(raw_rows) == 0:
        return table

    schema_definition = list(table.schema_definition or [])
    if len(schema_definition) == 0:
        if not data.infer_schema:
            raise DataHubValidationError(
                "Table schema is empty; set infer_schema=true or define schema_definition first"
            )
        schema_definition = _infer_schema_definition_from_records(raw_rows)
        table.schema_definition = schema_definition

    normalized_rows = _normalize_rows_against_schema(raw_rows, schema_definition)
    return await _append_rows(db, table, normalized_rows)


async def _resolve_import_connector(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubImportRequest,
):
    connector_type = data.connector_type
    connector_config = dict(data.connector_config or {})

    if data.connection_id is not None:
        connection_result = await db.execute(
            select(CloudWorksConnection).where(CloudWorksConnection.id == data.connection_id)
        )
        connection = connection_result.scalar_one_or_none()
        if connection is None:
            raise DataHubValidationError("Connection not found")
        if connection.model_id != table.model_id:
            raise DataHubValidationError(
                "Connection does not belong to the same model as this Data Hub table"
            )
        connector_type = str(connection.connector_type.value)
        if isinstance(connection.config, dict):
            merged_config = dict(connection.config)
            merged_config.update(connector_config)
            connector_config = merged_config

    if connector_type is None:
        raise DataHubValidationError(
            "connector_type is required when connection_id is not provided"
        )

    try:
        return create_connector(
            connector_type=connector_type,
            config=connector_config,
        )
    except ConnectorError as exc:
        raise DataHubValidationError(str(exc)) from exc


async def import_table_rows_from_connector(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubImportRequest,
) -> Tuple[DataHubTable, int]:
    connector = await _resolve_import_connector(db, table, data)
    try:
        dataset = await asyncio.to_thread(connector.read)
    except Exception as exc:  # noqa: BLE001
        raise DataHubValidationError(
            "Connector import failed: %s" % exc
        ) from exc

    if isinstance(dataset, pd.DataFrame):
        frame = dataset.copy()
    else:
        frame = pd.DataFrame(dataset)

    imported_rows = _frame_to_records(frame)
    write_request = DataHubRowsWriteRequest(
        rows=imported_rows,
        infer_schema=data.infer_schema,
    )
    if data.replace_existing:
        updated = await replace_table_rows(db, table, write_request)
    else:
        updated = await append_table_rows(db, table, write_request)
    return updated, len(imported_rows)


async def transform_table_rows(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubTransformRequest,
) -> Tuple[DataHubTable, int, int]:
    table_with_rows = await _get_table_with_rows_by_id(db, table.id)
    if table_with_rows is None:
        raise DataHubValidationError("Table not found")

    input_rows = [row.row_data for row in table_with_rows.rows]
    frame = pd.DataFrame(input_rows)
    rows_before = int(len(frame.index))

    for index, operation in enumerate(data.operations):
        step_name = (
            operation.name
            if operation.name is not None and len(operation.name.strip()) > 0
            else "operation-%s" % (index + 1)
        )
        try:
            if operation.operation_type == "transform":
                frame = apply_transform_step(frame, operation.config, step_name=step_name)
            elif operation.operation_type == "filter":
                frame = apply_filter_step(frame, operation.config, step_name=step_name)
            elif operation.operation_type == "map":
                frame = apply_map_step(frame, operation.config, step_name=step_name)
            elif operation.operation_type == "aggregate":
                frame = apply_aggregate_step(frame, operation.config, step_name=step_name)
            else:
                raise DataHubValidationError(
                    "Unsupported transform operation '%s'"
                    % operation.operation_type
                )
        except Exception as exc:  # noqa: BLE001
            raise DataHubValidationError(str(exc)) from exc

    transformed_rows = _frame_to_records(frame)
    inferred_schema = _infer_schema_definition_from_frame(frame)

    if data.replace_existing:
        table_with_rows.schema_definition = inferred_schema
        normalized_rows = _normalize_rows_against_schema(
            transformed_rows,
            inferred_schema,
        ) if len(inferred_schema) > 0 else []
        updated_table = await _replace_rows(db, table_with_rows, normalized_rows)
    else:
        if len(table_with_rows.schema_definition or []) == 0:
            table_with_rows.schema_definition = inferred_schema
        normalized_rows = _normalize_rows_against_schema(
            transformed_rows,
            list(table_with_rows.schema_definition or []),
        )
        updated_table = await _append_rows(db, table_with_rows, normalized_rows)

    return updated_table, rows_before, int(len(frame.index))


async def _upsert_lineage(
    db: AsyncSession,
    table: DataHubTable,
    module: Module,
    publish_config: DataHubPublishRequest,
    records_published: int,
) -> DataHubLineage:
    lineage_result = await db.execute(
        select(DataHubLineage).where(
            DataHubLineage.table_id == table.id,
            DataHubLineage.target_module_id == module.id,
        )
    )
    lineage = lineage_result.scalar_one_or_none()
    if lineage is None:
        lineage = DataHubLineage(
            table_id=table.id,
            target_model_id=module.model_id,
            target_module_id=module.id,
        )

    lineage.target_model_id = module.model_id
    lineage.mapping_config = _serialize_publish_mapping(publish_config)
    lineage.records_published = records_published
    lineage.last_published_at = datetime.now(timezone.utc)
    db.add(lineage)
    await db.commit()
    await db.refresh(lineage)
    return lineage


async def publish_table_to_module(
    db: AsyncSession,
    table: DataHubTable,
    data: DataHubPublishRequest,
) -> Tuple[DataHubLineage, int, int]:
    module_result = await db.execute(
        select(Module).where(Module.id == data.module_id)
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        raise DataHubValidationError("Module not found")

    table_with_rows = await _get_table_with_rows_by_id(db, table.id)
    if table_with_rows is None:
        raise DataHubValidationError("Table not found")

    rows = [row.row_data for row in table_with_rows.rows]
    rows_processed = len(rows)
    cell_writes: List[CellWrite] = []

    for row_index, row_data in enumerate(rows):
        dimension_members = list(data.static_dimension_members)
        for dimension_column in data.dimension_columns:
            raw_value = row_data.get(dimension_column)
            if _is_nullish(raw_value):
                raise DataHubValidationError(
                    "Row %s has null value for dimension column '%s'"
                    % (row_index, dimension_column)
                )

            value_map = data.dimension_member_map.get(dimension_column, {})
            mapped_value = value_map.get(str(raw_value))
            resolved_value = mapped_value if mapped_value is not None else raw_value
            member_id = _parse_uuid_value(
                resolved_value,
                field_name="dimension_columns.%s" % dimension_column,
            )
            dimension_members.append(member_id)

        for source_column, line_item_id in data.line_item_map.items():
            value = row_data.get(source_column)
            if _is_nullish(value) and not data.allow_null_values:
                continue
            cell_writes.append(
                CellWrite(
                    line_item_id=line_item_id,
                    dimension_members=dimension_members,
                    version_id=data.version_id,
                    value=value,
                )
            )

    written_cells = 0
    if len(cell_writes) > 0:
        for batch in _chunk_cells(cell_writes, data.batch_size):
            write_result = await write_cells_bulk(db, batch)
            written_cells += len(write_result)

    lineage = await _upsert_lineage(
        db,
        table=table_with_rows,
        module=module,
        publish_config=data,
        records_published=written_cells,
    )
    return lineage, rows_processed, written_cells


async def list_lineages_for_table(
    db: AsyncSession,
    table_id: uuid.UUID,
) -> List[DataHubLineage]:
    result = await db.execute(
        select(DataHubLineage)
        .where(DataHubLineage.table_id == table_id)
        .options(
            selectinload(DataHubLineage.target_model),
            selectinload(DataHubLineage.target_module),
        )
        .order_by(DataHubLineage.updated_at.desc())
    )
    return list(result.scalars().all())
