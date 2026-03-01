from typing import Any, Dict, Optional

import httpx
import pandas as pd

from app.connectors.base import (
    CloudWorksConnector,
    ConnectorError,
    dataframe_from_bytes,
    dataframe_to_bytes,
    ensure_dataframe,
    normalize_format,
)


class HTTPRESTConnector(CloudWorksConnector):
    """HTTP connector using httpx for REST ingestion and publishing."""

    def _resolve_timeout(self) -> float:
        timeout_value = self.config.get("timeout_seconds", 30)
        try:
            timeout = float(timeout_value)
        except (TypeError, ValueError) as exc:
            raise ConnectorError("Invalid timeout_seconds value: %s" % timeout_value) from exc
        if timeout <= 0:
            raise ConnectorError("timeout_seconds must be > 0")
        return timeout

    def _resolve_url(self, read_or_write_key: str) -> str:
        url = self.config.get(read_or_write_key) or self.config.get("url")
        if url is None:
            raise ConnectorError(
                "HTTP connector requires '%s' or 'url' in config" % read_or_write_key
            )
        return str(url)

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        configured = self.config.get("headers")
        if isinstance(configured, dict):
            headers = {str(k): str(v) for k, v in configured.items()}

        auth_type = str(self.config.get("auth_type", "")).strip().lower()
        if auth_type == "api_key":
            header_name = str(self.config.get("api_key_header", "X-API-Key"))
            headers[header_name] = str(self._require_value("api_key"))
        elif auth_type in {"bearer", "oauth"}:
            token = self.config.get("token") or self.config.get("access_token")
            if token is None:
                raise ConnectorError(
                    "HTTP connector auth_type '%s' requires token/access_token"
                    % auth_type
                )
            headers["Authorization"] = "Bearer %s" % token

        return headers

    def _build_auth(self) -> Optional[httpx.Auth]:
        auth_type = str(self.config.get("auth_type", "")).strip().lower()
        if auth_type == "basic":
            username = str(self._require_value("username"))
            password = str(self._require_value("password"))
            return httpx.BasicAuth(username=username, password=password)
        return None

    def read(self) -> pd.DataFrame:
        url = self._resolve_url("read_url")
        method = str(self.config.get("read_method", "GET")).upper()
        headers = self._build_headers()
        auth = self._build_auth()
        params = self.config.get("params")
        timeout = self._resolve_timeout()

        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            auth=auth,
            timeout=timeout,
        )
        response.raise_for_status()

        response_format = normalize_format(
            file_format=self.config.get("response_format"),
            path_hint=url,
            default_format="json",
        )
        if response_format == "json":
            return ensure_dataframe(response.json())
        return dataframe_from_bytes(response.content, response_format)

    def write(self, data: pd.DataFrame) -> None:
        if not isinstance(data, pd.DataFrame):
            raise ConnectorError("HTTPRESTConnector.write expects a pandas DataFrame")

        url = self._resolve_url("write_url")
        method = str(self.config.get("write_method", "POST")).upper()
        timeout = self._resolve_timeout()
        auth = self._build_auth()
        payload_format = normalize_format(
            file_format=self.config.get("payload_format"),
            path_hint=url,
            default_format="json",
        )

        headers = self._build_headers()
        request_kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
            "auth": auth,
            "timeout": timeout,
        }

        if payload_format == "json":
            request_kwargs["json"] = data.to_dict(orient="records")
        else:
            if payload_format == "csv":
                headers.setdefault("Content-Type", "text/csv")
            elif payload_format == "parquet":
                headers.setdefault("Content-Type", "application/octet-stream")
            payload = dataframe_to_bytes(data, payload_format)
            request_kwargs["content"] = payload

        response = httpx.request(**request_kwargs)
        response.raise_for_status()
