from abc import ABC, abstractmethod
import io
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


class ConnectorError(RuntimeError):
    """Raised when a connector cannot read/write with the provided configuration."""


def infer_format_from_path(path_hint: Optional[str]) -> Optional[str]:
    if path_hint is None:
        return None

    suffix = Path(path_hint).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in {".parquet", ".pq"}:
        return "parquet"
    if suffix in {".json", ".jsonl"}:
        return "json"
    return None


def normalize_format(
    file_format: Optional[str],
    path_hint: Optional[str],
    default_format: str = "csv",
) -> str:
    candidate = file_format.strip().lower().lstrip(".") if file_format else None
    resolved = candidate or infer_format_from_path(path_hint) or default_format
    if resolved not in {"csv", "parquet", "json"}:
        raise ConnectorError(
            "Unsupported file format '%s'. Expected one of csv/parquet/json." % resolved
        )
    return resolved


def ensure_dataframe(payload: Any) -> pd.DataFrame:
    if isinstance(payload, pd.DataFrame):
        return payload

    if payload is None:
        return pd.DataFrame()

    if isinstance(payload, list):
        if len(payload) == 0:
            return pd.DataFrame()
        if all(isinstance(item, dict) for item in payload):
            return pd.DataFrame(payload)
        return pd.DataFrame({"value": payload})

    if isinstance(payload, dict):
        data_payload = payload.get("data")
        if isinstance(data_payload, list):
            return ensure_dataframe(data_payload)
        return pd.DataFrame([payload])

    raise ConnectorError(
        "Could not convert payload type '%s' into a DataFrame" % type(payload).__name__
    )


def dataframe_from_bytes(raw_data: bytes, file_format: str) -> pd.DataFrame:
    if file_format == "csv":
        return pd.read_csv(io.BytesIO(raw_data))

    if file_format == "parquet":
        return pd.read_parquet(io.BytesIO(raw_data))

    if file_format == "json":
        try:
            parsed = json.loads(raw_data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ConnectorError("Invalid JSON payload: %s" % exc) from exc
        return ensure_dataframe(parsed)

    raise ConnectorError("Unsupported file format '%s'" % file_format)


def dataframe_to_bytes(data: pd.DataFrame, file_format: str) -> bytes:
    if file_format == "csv":
        return data.to_csv(index=False).encode("utf-8")

    if file_format == "parquet":
        buffer = io.BytesIO()
        data.to_parquet(buffer, index=False)
        return buffer.getvalue()

    if file_format == "json":
        payload = data.to_dict(orient="records")
        return json.dumps(payload).encode("utf-8")

    raise ConnectorError("Unsupported file format '%s'" % file_format)


class CloudWorksConnector(ABC):
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = dict(config or {})

    @abstractmethod
    def read(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def write(self, data: pd.DataFrame) -> None:
        raise NotImplementedError

    def _require_value(self, key: str) -> Any:
        value = self.config.get(key)
        if value is None or (isinstance(value, str) and len(value.strip()) == 0):
            raise ConnectorError(
                "Missing required connector config value '%s'" % key
            )
        return value
