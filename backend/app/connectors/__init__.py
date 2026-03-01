from typing import Any, Dict, Optional, Type

from app.connectors.base import CloudWorksConnector, ConnectorError
from app.connectors.database import DatabaseConnector
from app.connectors.http_rest import HTTPRESTConnector
from app.connectors.local_file import LocalFileConnector
from app.connectors.s3 import S3Connector
from app.connectors.sftp import SFTPConnector


CONNECTOR_REGISTRY: Dict[str, Type[CloudWorksConnector]] = {
    "s3": S3Connector,
    "database": DatabaseConnector,
    "sftp": SFTPConnector,
    "http": HTTPRESTConnector,
    "http_rest": HTTPRESTConnector,
    "local_file": LocalFileConnector,
    "file": LocalFileConnector,
}


def create_connector(
    connector_type: Any,
    config: Optional[Dict[str, Any]] = None,
) -> CloudWorksConnector:
    resolved_type = getattr(connector_type, "value", connector_type)
    if resolved_type is None:
        raise ConnectorError("Connector type is required")

    normalized = str(resolved_type).strip().lower()
    connector_cls = CONNECTOR_REGISTRY.get(normalized)
    if connector_cls is None:
        raise ConnectorError(
            "Connector type '%s' is not implemented in the F063 SDK"
            % normalized
        )

    return connector_cls(config=config or {})


__all__ = [
    "CloudWorksConnector",
    "ConnectorError",
    "DatabaseConnector",
    "HTTPRESTConnector",
    "LocalFileConnector",
    "S3Connector",
    "SFTPConnector",
    "create_connector",
]
