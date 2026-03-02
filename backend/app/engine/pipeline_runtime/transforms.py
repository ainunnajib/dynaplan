from typing import Any, Dict, List, Tuple

import pandas as pd

from app.engine.pipeline_runtime.config_parser import PipelineRuntimeConfigError, coerce_list
from app.engine.pipeline_runtime.dataframe_utils import (
    normalize_aggregation_method,
    normalize_column_mapping,
    resolve_pandas_dtype,
)


def _require_columns(frame: pd.DataFrame, columns: List[str], context: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise PipelineRuntimeConfigError(
            "Step '%s' references missing columns: %s"
            % (context, ", ".join(sorted(missing)))
        )


def _coerce_join_suffixes(raw_suffixes: Any) -> Tuple[str, str]:
    if raw_suffixes is None:
        return ("_x", "_y")

    if isinstance(raw_suffixes, (list, tuple)) and len(raw_suffixes) == 2:
        return (str(raw_suffixes[0]), str(raw_suffixes[1]))

    raise PipelineRuntimeConfigError(
        "Transform join 'suffixes' must contain exactly two values"
    )


def _resolve_join_frame(join_config: Dict[str, Any]) -> pd.DataFrame:
    right_payload = join_config.get("right")
    if right_payload is None:
        right_payload = join_config.get("right_data")
    if right_payload is None:
        right_payload = join_config.get("data")

    if isinstance(right_payload, pd.DataFrame):
        return right_payload.copy()

    if isinstance(right_payload, dict):
        nested_data = right_payload.get("data")
        if isinstance(nested_data, list):
            return pd.DataFrame(nested_data)
        return pd.DataFrame([right_payload])

    if isinstance(right_payload, list):
        return pd.DataFrame(right_payload)

    raise PipelineRuntimeConfigError(
        "Transform join config requires 'right'/'right_data' as array or object"
    )


def _apply_casts(frame: pd.DataFrame, casts: Dict[str, Any], context: str) -> pd.DataFrame:
    if len(casts) == 0:
        return frame

    cast_columns = list(casts.keys())
    _require_columns(frame, cast_columns, context=context)

    result = frame.copy()
    for column_name, cast_type in casts.items():
        dtype = resolve_pandas_dtype(cast_type)
        if dtype.startswith("datetime64"):
            result[column_name] = pd.to_datetime(result[column_name], errors="coerce")
            continue
        if dtype in {"Int64", "float64"}:
            numeric_series = pd.to_numeric(result[column_name], errors="coerce")
            if dtype == "Int64":
                result[column_name] = numeric_series.round().astype("Int64")
            else:
                result[column_name] = numeric_series.astype("float64")
            continue
        result[column_name] = result[column_name].astype(dtype)
    return result


def _apply_expressions(
    frame: pd.DataFrame,
    expressions: Dict[str, Any],
    context: str,
) -> pd.DataFrame:
    if len(expressions) == 0:
        return frame

    result = frame.copy()
    for target_column, expression in expressions.items():
        if not isinstance(expression, str) or len(expression.strip()) == 0:
            raise PipelineRuntimeConfigError(
                "Step '%s' expression for column '%s' must be a non-empty string"
                % (context, target_column)
            )
        try:
            result[str(target_column)] = result.eval(expression, engine="python")
        except Exception as exc:  # noqa: BLE001
            raise PipelineRuntimeConfigError(
                "Step '%s' failed expression '%s': %s"
                % (context, expression, exc)
            ) from exc
    return result


def _apply_join(frame: pd.DataFrame, join_config: Dict[str, Any], context: str) -> pd.DataFrame:
    if not isinstance(join_config, dict):
        raise PipelineRuntimeConfigError("Step '%s' join config must be an object" % context)

    right_frame = _resolve_join_frame(join_config)
    if len(right_frame.index) == 0:
        return frame.copy()

    merge_how = str(join_config.get("how", "inner")).strip().lower()
    if merge_how not in {"left", "right", "outer", "inner", "cross"}:
        raise PipelineRuntimeConfigError(
            "Step '%s' has unsupported join type '%s'" % (context, merge_how)
        )

    on_columns_raw = join_config.get("on")
    on_columns = coerce_list(on_columns_raw, "join.on")
    left_on = coerce_list(join_config.get("left_on"), "join.left_on")
    right_on = coerce_list(join_config.get("right_on"), "join.right_on")
    suffixes = _coerce_join_suffixes(join_config.get("suffixes"))

    if merge_how != "cross":
        if len(on_columns) > 0:
            _require_columns(frame, [str(column) for column in on_columns], context=context)
            _require_columns(
                right_frame,
                [str(column) for column in on_columns],
                context=context,
            )
        else:
            if len(left_on) == 0 or len(right_on) == 0:
                raise PipelineRuntimeConfigError(
                    "Step '%s' join requires 'on' or both 'left_on' and 'right_on'"
                    % context
                )
            if len(left_on) != len(right_on):
                raise PipelineRuntimeConfigError(
                    "Step '%s' join 'left_on' and 'right_on' lengths must match"
                    % context
                )
            _require_columns(frame, [str(column) for column in left_on], context=context)
            _require_columns(
                right_frame,
                [str(column) for column in right_on],
                context=context,
            )

    if len(on_columns) > 0:
        return frame.merge(
            right_frame,
            how=merge_how,
            on=[str(column) for column in on_columns],
            suffixes=suffixes,
        )

    if merge_how == "cross":
        return frame.merge(right_frame, how="cross", suffixes=suffixes)

    return frame.merge(
        right_frame,
        how=merge_how,
        left_on=[str(column) for column in left_on],
        right_on=[str(column) for column in right_on],
        suffixes=suffixes,
    )


def apply_transform_step(frame: pd.DataFrame, config: Dict[str, Any], step_name: str) -> pd.DataFrame:
    result = frame.copy()

    rename_mapping = normalize_column_mapping(config.get("rename"), "rename")
    if len(rename_mapping) > 0:
        _require_columns(result, list(rename_mapping.keys()), context=step_name)
        result = result.rename(columns=rename_mapping)

    casts = normalize_column_mapping(config.get("casts"), "casts")
    result = _apply_casts(result, casts=casts, context=step_name)

    expressions = normalize_column_mapping(config.get("expressions"), "expressions")
    result = _apply_expressions(result, expressions=expressions, context=step_name)

    join_config = config.get("join")
    if join_config is not None:
        result = _apply_join(result, join_config=join_config, context=step_name)

    return result


def apply_filter_step(frame: pd.DataFrame, config: Dict[str, Any], step_name: str) -> pd.DataFrame:
    expression = config.get("expression") or config.get("query")
    if expression is None:
        raise PipelineRuntimeConfigError(
            "Filter step '%s' requires 'expression' (or 'query') in config"
            % step_name
        )

    expression_text = str(expression).strip()
    if len(expression_text) == 0:
        raise PipelineRuntimeConfigError(
            "Filter step '%s' expression cannot be empty" % step_name
        )

    try:
        return frame.query(expression_text, engine="python")
    except Exception as exc:  # noqa: BLE001
        raise PipelineRuntimeConfigError(
            "Filter step '%s' failed expression '%s': %s"
            % (step_name, expression_text, exc)
        ) from exc


def _normalize_map_operations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    configured = config.get("mappings")
    if isinstance(configured, list):
        operations = []
        for entry in configured:
            if not isinstance(entry, dict):
                raise PipelineRuntimeConfigError("Map step 'mappings' entries must be objects")
            operations.append(entry)
        return operations

    if "column" not in config:
        raise PipelineRuntimeConfigError(
            "Map step requires either 'mappings' or ('column' + 'mapping')"
        )

    return [config]


def apply_map_step(frame: pd.DataFrame, config: Dict[str, Any], step_name: str) -> pd.DataFrame:
    result = frame.copy()
    operations = _normalize_map_operations(config)

    for operation in operations:
        column_name = operation.get("column")
        mapping = operation.get("mapping") or operation.get("map")
        target_column = operation.get("target_column") or column_name
        default_value = operation.get("default")
        preserve_unmapped = bool(operation.get("preserve_unmapped", True))

        if column_name is None:
            raise PipelineRuntimeConfigError("Map step '%s' operation missing 'column'" % step_name)
        if not isinstance(mapping, dict):
            raise PipelineRuntimeConfigError(
                "Map step '%s' column '%s' requires object 'mapping'"
                % (step_name, column_name)
            )

        source_column = str(column_name)
        target_column_name = str(target_column)
        _require_columns(result, [source_column], context=step_name)

        mapped = result[source_column].map(mapping)
        if preserve_unmapped:
            mapped = mapped.where(mapped.notna(), result[source_column])
        if "default" in operation:
            mapped = mapped.fillna(default_value)

        result[target_column_name] = mapped

    return result


def _aggregate_series(series: pd.Series, method: str) -> Any:
    if method == "sum":
        return series.sum()
    if method == "count":
        return series.count()
    if method == "mean":
        return series.mean()
    if method == "min":
        return series.min()
    if method == "max":
        return series.max()
    raise ValueError("Unsupported aggregation method '%s'" % method)


def apply_aggregate_step(frame: pd.DataFrame, config: Dict[str, Any], step_name: str) -> pd.DataFrame:
    group_by_raw = config.get("group_by")
    group_by_columns = [str(column) for column in coerce_list(group_by_raw, "group_by")]

    aggregations_raw = config.get("aggregations")
    if not isinstance(aggregations_raw, dict) or len(aggregations_raw) == 0:
        raise PipelineRuntimeConfigError(
            "Aggregate step '%s' requires non-empty object 'aggregations'"
            % step_name
        )

    aggregation_methods = {
        str(column): normalize_aggregation_method(method)
        for column, method in aggregations_raw.items()
    }

    _require_columns(frame, list(aggregation_methods.keys()), context=step_name)
    if len(group_by_columns) > 0:
        _require_columns(frame, group_by_columns, context=step_name)

    if len(group_by_columns) == 0:
        row = {
            column: _aggregate_series(frame[column], method)
            for column, method in aggregation_methods.items()
        }
        return pd.DataFrame([row])

    grouped = frame.groupby(group_by_columns, as_index=False).agg(aggregation_methods)
    return grouped
