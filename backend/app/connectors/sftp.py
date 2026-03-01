import io
from pathlib import PurePosixPath
from typing import Any, Optional, Tuple

import pandas as pd

from app.connectors.base import (
    CloudWorksConnector,
    ConnectorError,
    dataframe_from_bytes,
    dataframe_to_bytes,
    normalize_format,
)

try:
    import paramiko
except ImportError:  # pragma: no cover - optional dependency
    paramiko = None  # type: ignore[assignment]


class SFTPConnector(CloudWorksConnector):
    """SFTP connector backed by paramiko."""

    def _connect(self) -> Tuple[Any, Any]:
        if paramiko is None:
            raise ConnectorError(
                "paramiko is not installed. Install paramiko to use the SFTP connector."
            )

        host = str(self._require_value("host"))
        port = int(self.config.get("port", 22))
        username = str(self._require_value("username"))

        transport = paramiko.Transport((host, port))

        private_key = self.config.get("private_key")
        private_key_path = self.config.get("private_key_path")
        passphrase = self.config.get("private_key_passphrase")

        if private_key is not None:
            key = paramiko.RSAKey.from_private_key(
                io.StringIO(str(private_key)),
                password=str(passphrase) if passphrase is not None else None,
            )
            transport.connect(username=username, pkey=key)
        elif private_key_path is not None:
            key = paramiko.RSAKey.from_private_key_file(
                filename=str(private_key_path),
                password=str(passphrase) if passphrase is not None else None,
            )
            transport.connect(username=username, pkey=key)
        else:
            password = self._require_value("password")
            transport.connect(username=username, password=str(password))

        sftp = paramiko.SFTPClient.from_transport(transport)
        return transport, sftp

    def _resolve_remote_path_and_format(self) -> Tuple[str, str]:
        remote_path = str(self._require_value("path"))
        file_format = normalize_format(
            file_format=self.config.get("format"),
            path_hint=remote_path,
            default_format="csv",
        )
        return remote_path, file_format

    def _ensure_remote_parent(self, sftp_client: Any, remote_path: str) -> None:
        parent = str(PurePosixPath(remote_path).parent)
        if parent in {"", ".", "/"}:
            return

        current = ""
        for part in parent.split("/"):
            if len(part) == 0:
                continue
            current = "%s/%s" % (current, part) if current else "/%s" % part
            try:
                sftp_client.stat(current)
            except IOError:
                sftp_client.mkdir(current)

    def read(self) -> pd.DataFrame:
        remote_path, file_format = self._resolve_remote_path_and_format()
        transport: Optional[Any] = None
        sftp_client: Optional[Any] = None

        try:
            transport, sftp_client = self._connect()
            with sftp_client.open(remote_path, "rb") as file_obj:
                raw_data = file_obj.read()
            return dataframe_from_bytes(raw_data, file_format)
        finally:
            if sftp_client is not None:
                sftp_client.close()
            if transport is not None:
                transport.close()

    def write(self, data: pd.DataFrame) -> None:
        if not isinstance(data, pd.DataFrame):
            raise ConnectorError("SFTPConnector.write expects a pandas DataFrame")

        remote_path, file_format = self._resolve_remote_path_and_format()
        payload = dataframe_to_bytes(data, file_format)

        transport: Optional[Any] = None
        sftp_client: Optional[Any] = None
        try:
            transport, sftp_client = self._connect()
            self._ensure_remote_parent(sftp_client, remote_path)
            with sftp_client.open(remote_path, "wb") as file_obj:
                file_obj.write(payload)
        finally:
            if sftp_client is not None:
                sftp_client.close()
            if transport is not None:
                transport.close()
