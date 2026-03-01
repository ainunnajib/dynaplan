from typing import Any, Dict

import pandas as pd

from app.connectors.base import (
    CloudWorksConnector,
    ConnectorError,
    dataframe_from_bytes,
    dataframe_to_bytes,
    normalize_format,
)

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore[assignment]


class S3Connector(CloudWorksConnector):
    """Amazon S3 connector using boto3."""

    def _build_client(self):
        if boto3 is None:
            raise ConnectorError(
                "boto3 is not installed. Install boto3 to use the S3 connector."
            )

        region = self.config.get("region")
        access_key = self.config.get("access_key") or self.config.get("aws_access_key_id")
        secret_key = self.config.get("secret_key") or self.config.get("aws_secret_access_key")
        session_token = self.config.get("session_token") or self.config.get("aws_session_token")

        client_kwargs: Dict[str, Any] = {}
        if region is not None:
            client_kwargs["region_name"] = str(region)
        if access_key is not None:
            client_kwargs["aws_access_key_id"] = str(access_key)
        if secret_key is not None:
            client_kwargs["aws_secret_access_key"] = str(secret_key)
        if session_token is not None:
            client_kwargs["aws_session_token"] = str(session_token)

        role_arn = self.config.get("role_arn")
        if role_arn is not None:
            sts_client = boto3.client("sts", **client_kwargs)
            assume_kwargs = {
                "RoleArn": str(role_arn),
                "RoleSessionName": str(
                    self.config.get("role_session_name", "dynaplan-cloudworks")
                ),
            }
            external_id = self.config.get("external_id")
            if external_id is not None:
                assume_kwargs["ExternalId"] = str(external_id)
            credentials = sts_client.assume_role(**assume_kwargs)["Credentials"]
            client_kwargs["aws_access_key_id"] = credentials["AccessKeyId"]
            client_kwargs["aws_secret_access_key"] = credentials["SecretAccessKey"]
            client_kwargs["aws_session_token"] = credentials["SessionToken"]

        return boto3.client("s3", **client_kwargs)

    def _resolve_bucket_and_key(self) -> tuple:
        bucket = str(self._require_value("bucket"))
        key = self.config.get("key") or self.config.get("object_key")
        if key is None:
            raise ConnectorError("S3 connector requires 'key' or 'object_key' in config")
        return bucket, str(key)

    def read(self) -> pd.DataFrame:
        bucket, key = self._resolve_bucket_and_key()
        file_format = normalize_format(
            file_format=self.config.get("format"),
            path_hint=key,
            default_format="csv",
        )

        client = self._build_client()
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        return dataframe_from_bytes(body, file_format)

    def write(self, data: pd.DataFrame) -> None:
        if not isinstance(data, pd.DataFrame):
            raise ConnectorError("S3Connector.write expects a pandas DataFrame")

        bucket, key = self._resolve_bucket_and_key()
        file_format = normalize_format(
            file_format=self.config.get("format"),
            path_hint=key,
            default_format="csv",
        )
        payload = dataframe_to_bytes(data, file_format)

        client = self._build_client()
        client.put_object(Bucket=bucket, Key=key, Body=payload)
