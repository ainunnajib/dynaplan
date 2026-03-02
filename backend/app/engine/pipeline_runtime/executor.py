import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import create_connector
from app.engine.pipeline_runtime.config_parser import (
    PipelineRuntimeConfigError,
    parse_step_config,
    resolve_connector_config,
)
from app.engine.pipeline_runtime.dataframe_utils import (
    dataframe_row_count,
    ensure_dataframe,
)
from app.engine.pipeline_runtime.transforms import (
    apply_aggregate_step,
    apply_filter_step,
    apply_map_step,
    apply_transform_step,
)
from app.models.pipeline import PipelineStep, StepType
from app.schemas.cell import CellWrite
from app.services.cell import write_cells_bulk


@dataclass
class StepExecutionResult:
    output_frame: pd.DataFrame
    records_in: int
    records_out: int
    log_output: str


class PipelineRuntimeExecutionError(RuntimeError):
    """Raised when pipeline runtime execution fails."""


class PipelineRuntimeExecutor:
    def __init__(self, db: AsyncSession, model_id: uuid.UUID) -> None:
        self.db = db
        self.model_id = model_id

    async def execute_step(
        self,
        step: PipelineStep,
        input_frame: Optional[pd.DataFrame],
    ) -> StepExecutionResult:
        step_name = step.name
        step_type = StepType(step.step_type)
        step_config = parse_step_config(step.config, step_name=step_name)

        if step_type == StepType.source:
            return await self._execute_source(step_name=step_name, config=step_config)

        current_frame = ensure_dataframe(input_frame, context=step_name)
        records_in = dataframe_row_count(current_frame)

        if step_type == StepType.transform:
            output_frame = apply_transform_step(current_frame, step_config, step_name=step_name)
            return StepExecutionResult(
                output_frame=output_frame,
                records_in=records_in,
                records_out=dataframe_row_count(output_frame),
                log_output="Applied transform operations",
            )

        if step_type == StepType.filter:
            output_frame = apply_filter_step(current_frame, step_config, step_name=step_name)
            return StepExecutionResult(
                output_frame=output_frame,
                records_in=records_in,
                records_out=dataframe_row_count(output_frame),
                log_output="Applied filter expression",
            )

        if step_type == StepType.map:
            output_frame = apply_map_step(current_frame, step_config, step_name=step_name)
            return StepExecutionResult(
                output_frame=output_frame,
                records_in=records_in,
                records_out=dataframe_row_count(output_frame),
                log_output="Applied value mapping",
            )

        if step_type == StepType.aggregate:
            output_frame = apply_aggregate_step(current_frame, step_config, step_name=step_name)
            return StepExecutionResult(
                output_frame=output_frame,
                records_in=records_in,
                records_out=dataframe_row_count(output_frame),
                log_output="Applied aggregation",
            )

        if step_type == StepType.publish:
            records_out = await self._execute_publish(
                step_name=step_name,
                frame=current_frame,
                config=step_config,
            )
            return StepExecutionResult(
                output_frame=current_frame,
                records_in=records_in,
                records_out=records_out,
                log_output="Published %s cells to model %s" % (records_out, self.model_id),
            )

        raise PipelineRuntimeExecutionError(
            "Unsupported pipeline step type '%s'" % step_type.value
        )

    async def _execute_source(
        self,
        step_name: str,
        config: Dict[str, Any],
    ) -> StepExecutionResult:
        inline_data = config.get("inline_data")
        if inline_data is not None:
            frame = ensure_dataframe(inline_data, context=step_name)
            return StepExecutionResult(
                output_frame=frame,
                records_in=0,
                records_out=dataframe_row_count(frame),
                log_output="Loaded source inline_data rows",
            )

        connector_type, connector_config = resolve_connector_config(config)
        connector = create_connector(connector_type=connector_type, config=connector_config)
        try:
            dataset = await asyncio.to_thread(connector.read)
        except Exception as exc:  # noqa: BLE001
            raise PipelineRuntimeExecutionError(
                "Source step '%s' failed connector read (%s): %s"
                % (step_name, connector_type, exc)
            ) from exc

        frame = ensure_dataframe(dataset, context=step_name)
        return StepExecutionResult(
            output_frame=frame,
            records_in=0,
            records_out=dataframe_row_count(frame),
            log_output="Loaded source dataset via connector '%s'" % connector_type,
        )

    async def _execute_publish(
        self,
        step_name: str,
        frame: pd.DataFrame,
        config: Dict[str, Any],
    ) -> int:
        if len(frame.index) == 0:
            return 0

        cell_writes = self._build_cell_writes(step_name=step_name, frame=frame, config=config)
        if len(cell_writes) == 0:
            return 0

        batch_size_raw = config.get("batch_size", 500)
        try:
            batch_size = int(batch_size_raw)
        except (TypeError, ValueError):
            raise PipelineRuntimeConfigError(
                "Publish step '%s' has invalid batch_size '%s'"
                % (step_name, batch_size_raw)
            )
        if batch_size <= 0:
            raise PipelineRuntimeConfigError(
                "Publish step '%s' batch_size must be > 0" % step_name
            )

        published = 0
        for batch in _chunked(cell_writes, batch_size):
            results = await write_cells_bulk(self.db, cells=batch)
            published += len(results)
        return published

    def _build_cell_writes(
        self,
        step_name: str,
        frame: pd.DataFrame,
        config: Dict[str, Any],
    ) -> List[CellWrite]:
        line_item_map_raw = config.get("line_item_map")
        if isinstance(line_item_map_raw, dict) and len(line_item_map_raw) > 0:
            line_item_map = {
                str(column): _parse_uuid(value, field_name="line_item_map.%s" % column)
                for column, value in line_item_map_raw.items()
            }
        else:
            line_item_id = config.get("line_item_id")
            value_column = config.get("value_column")
            if line_item_id is None or value_column is None:
                raise PipelineRuntimeConfigError(
                    "Publish step '%s' requires 'line_item_map' or ('line_item_id' + 'value_column')"
                    % step_name
                )
            line_item_map = {
                str(value_column): _parse_uuid(line_item_id, field_name="line_item_id")
            }

        required_columns = list(line_item_map.keys())
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            raise PipelineRuntimeConfigError(
                "Publish step '%s' is missing source columns: %s"
                % (step_name, ", ".join(sorted(missing_columns)))
            )

        dimension_columns_raw = config.get("dimension_columns", [])
        dimension_columns = [str(column) for column in _coerce_list(dimension_columns_raw)]
        for column in dimension_columns:
            if column not in frame.columns:
                raise PipelineRuntimeConfigError(
                    "Publish step '%s' missing dimension column '%s'"
                    % (step_name, column)
                )

        dimension_member_map = config.get("dimension_member_map")
        if dimension_member_map is None:
            dimension_member_map = {}
        if not isinstance(dimension_member_map, dict):
            raise PipelineRuntimeConfigError(
                "Publish step '%s' field 'dimension_member_map' must be an object"
                % step_name
            )

        static_members_raw = config.get("static_dimension_members", [])
        static_members = [
            _parse_uuid(member, field_name="static_dimension_members")
            for member in _coerce_list(static_members_raw)
        ]

        explicit_version_id = config.get("version_id")
        version_id = (
            _parse_uuid(explicit_version_id, field_name="version_id")
            if explicit_version_id is not None
            else None
        )

        allow_null_values = bool(config.get("allow_null_values", False))
        writes: List[CellWrite] = []

        for row in frame.to_dict(orient="records"):
            dimension_members = list(static_members)
            for dimension_column in dimension_columns:
                row_value = row.get(dimension_column)
                if _is_nullish(row_value):
                    raise PipelineRuntimeConfigError(
                        "Publish step '%s' encountered null dimension value for column '%s'"
                        % (step_name, dimension_column)
                    )

                member_lookup = dimension_member_map.get(dimension_column)
                resolved_member = row_value
                if isinstance(member_lookup, dict):
                    resolved_member = member_lookup.get(str(row_value), member_lookup.get(row_value))

                dimension_members.append(
                    _parse_uuid(
                        resolved_member,
                        field_name="dimension_member_map.%s" % dimension_column,
                    )
                )

            for source_column, line_item_id in line_item_map.items():
                value = row.get(source_column)
                if _is_nullish(value) and not allow_null_values:
                    continue

                writes.append(
                    CellWrite(
                        line_item_id=line_item_id,
                        dimension_members=dimension_members,
                        version_id=version_id,
                        value=value,
                    )
                )

        return writes


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _parse_uuid(raw_value: Any, field_name: str) -> uuid.UUID:
    if isinstance(raw_value, uuid.UUID):
        return raw_value
    if raw_value is None:
        raise PipelineRuntimeConfigError("Field '%s' must be a UUID" % field_name)
    text = str(raw_value).strip()
    if len(text) == 0:
        raise PipelineRuntimeConfigError("Field '%s' cannot be empty" % field_name)
    try:
        return uuid.UUID(text)
    except ValueError as exc:
        raise PipelineRuntimeConfigError(
            "Field '%s' has invalid UUID '%s'" % (field_name, raw_value)
        ) from exc


def _is_nullish(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except Exception:  # noqa: BLE001
        return value is None


def _chunked(items: List[CellWrite], size: int) -> Iterable[List[CellWrite]]:
    for index in range(0, len(items), size):
        yield items[index: index + size]
