from pathlib import Path
from typing import Optional

import pandas as pd

from app.connectors.base import (
    CloudWorksConnector,
    ConnectorError,
    dataframe_from_bytes,
    dataframe_to_bytes,
    normalize_format,
)


class LocalFileConnector(CloudWorksConnector):
    """Local filesystem connector for development and tests."""

    def _resolve_path_and_format(self) -> tuple:
        path_value = str(self._require_value("path"))
        file_format = normalize_format(
            file_format=self.config.get("format"),
            path_hint=path_value,
            default_format="csv",
        )
        return Path(path_value), file_format

    def read(self) -> pd.DataFrame:
        file_path, file_format = self._resolve_path_and_format()
        if not file_path.exists():
            raise ConnectorError("File does not exist: %s" % file_path)

        raw_data = file_path.read_bytes()
        return dataframe_from_bytes(raw_data, file_format)

    def write(self, data: pd.DataFrame) -> None:
        if not isinstance(data, pd.DataFrame):
            raise ConnectorError("LocalFileConnector.write expects a pandas DataFrame")

        file_path, file_format = self._resolve_path_and_format()
        parent: Optional[Path] = file_path.parent if file_path.parent != Path("") else None
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)

        raw_data = dataframe_to_bytes(data, file_format)
        file_path.write_bytes(raw_data)
