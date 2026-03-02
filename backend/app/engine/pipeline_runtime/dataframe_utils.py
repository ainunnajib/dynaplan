from typing import Any, Dict, Optional

import pandas as pd


def dataframe_row_count(frame: Optional[pd.DataFrame]) -> int:
    if frame is None:
        return 0
    return int(len(frame.index))


def ensure_dataframe(payload: Any, context: str) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()

    if isinstance(payload, pd.DataFrame):
        return payload.copy()

    if isinstance(payload, list):
        if len(payload) == 0:
            return pd.DataFrame()
        if all(isinstance(item, dict) for item in payload):
            return pd.DataFrame(payload)
        return pd.DataFrame({"value": payload})

    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return ensure_dataframe(data, context=context)
        return pd.DataFrame([payload])

    raise ValueError(
        "Step '%s' produced unsupported payload type '%s'"
        % (context, type(payload).__name__)
    )


def normalize_column_mapping(raw_mapping: Any, field_name: str) -> Dict[str, Any]:
    if raw_mapping is None:
        return {}
    if not isinstance(raw_mapping, dict):
        raise ValueError("Expected '%s' to be a JSON object" % field_name)
    return {str(key): value for key, value in raw_mapping.items()}


def resolve_pandas_dtype(dtype_name: Any) -> str:
    if dtype_name is None:
        raise ValueError("Cast dtype cannot be null")

    raw = str(dtype_name).strip().lower()
    mapping = {
        "int": "Int64",
        "integer": "Int64",
        "int64": "Int64",
        "float": "float64",
        "float64": "float64",
        "number": "float64",
        "str": "string",
        "string": "string",
        "bool": "boolean",
        "boolean": "boolean",
        "datetime": "datetime64[ns]",
        "date": "datetime64[ns]",
    }
    return mapping.get(raw, raw)


def normalize_aggregation_method(method: Any) -> str:
    if method is None:
        raise ValueError("Aggregation method cannot be null")

    normalized = str(method).strip().lower()
    aliases = {
        "avg": "mean",
        "average": "mean",
    }
    resolved = aliases.get(normalized, normalized)

    supported = {"sum", "count", "mean", "min", "max"}
    if resolved not in supported:
        raise ValueError(
            "Unsupported aggregation method '%s'. Expected one of: %s"
            % (normalized, sorted(supported))
        )
    return resolved
