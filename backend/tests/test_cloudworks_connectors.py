from typing import Any, Dict, List

import httpx
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from app.connectors import ConnectorError, create_connector
from app.connectors.database import DatabaseConnector
from app.connectors.http_rest import HTTPRESTConnector
from app.connectors.local_file import LocalFileConnector


def test_local_file_connector_roundtrip_csv(tmp_path) -> None:
    source_path = tmp_path / "input.csv"
    source_path.write_text("name,amount\nA,10\nB,25\n", encoding="utf-8")
    target_path = tmp_path / "output.csv"

    reader = LocalFileConnector(config={"path": str(source_path), "format": "csv"})
    frame = reader.read()

    assert list(frame.columns) == ["name", "amount"]
    assert frame.to_dict(orient="records") == [
        {"name": "A", "amount": 10},
        {"name": "B", "amount": 25},
    ]

    writer = LocalFileConnector(config={"path": str(target_path), "format": "csv"})
    writer.write(frame)
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").startswith("name,amount")


def test_database_connector_read_and_write_sqlite(tmp_path) -> None:
    db_path = tmp_path / "connector.sqlite3"
    connection_string = "sqlite:///%s" % db_path
    seed_frame = pd.DataFrame(
        [
            {"id": 1, "total": 100.0},
            {"id": 2, "total": 250.5},
        ]
    )

    seed_engine = create_engine(connection_string)
    try:
        with seed_engine.begin() as connection:
            seed_frame.to_sql("source_table", connection, if_exists="replace", index=False)
    finally:
        seed_engine.dispose()

    reader = DatabaseConnector(
        config={
            "connection_string": connection_string,
            "query": "SELECT id, total FROM source_table ORDER BY id",
        }
    )
    dataset = reader.read()
    assert dataset.to_dict(orient="records") == [
        {"id": 1, "total": 100.0},
        {"id": 2, "total": 250.5},
    ]

    writer = DatabaseConnector(
        config={
            "connection_string": connection_string,
            "table": "target_table",
            "if_exists": "replace",
        }
    )
    writer.write(dataset)

    verify_engine = create_engine(connection_string)
    try:
        with verify_engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM target_table")).scalar_one()
            assert count == 2
    finally:
        verify_engine.dispose()


def test_http_rest_connector_read_and_write_json(monkeypatch) -> None:
    captured_calls: List[Dict[str, Any]] = []

    def fake_request(*args, **kwargs):
        del args
        captured_calls.append(kwargs)
        method = kwargs.get("method")
        url = kwargs.get("url")
        request = httpx.Request(method=method, url=url)

        if method == "GET":
            return httpx.Response(
                status_code=200,
                request=request,
                json=[{"sku": "A1", "qty": 5}, {"sku": "B2", "qty": 9}],
            )

        return httpx.Response(status_code=202, request=request)

    monkeypatch.setattr(httpx, "request", fake_request)

    connector = HTTPRESTConnector(
        config={
            "url": "https://example.test/data",
            "read_method": "GET",
            "write_method": "POST",
            "payload_format": "json",
        }
    )
    dataset = connector.read()
    assert dataset.to_dict(orient="records") == [
        {"sku": "A1", "qty": 5},
        {"sku": "B2", "qty": 9},
    ]

    connector.write(dataset)

    assert len(captured_calls) == 2
    assert captured_calls[1]["method"] == "POST"
    assert captured_calls[1]["json"] == [
        {"sku": "A1", "qty": 5},
        {"sku": "B2", "qty": 9},
    ]


def test_create_connector_rejects_unimplemented_type() -> None:
    with pytest.raises(ConnectorError):
        create_connector(connector_type="gcs", config={})
