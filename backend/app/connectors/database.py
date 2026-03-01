from typing import Any, Dict, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.connectors.base import CloudWorksConnector, ConnectorError


class DatabaseConnector(CloudWorksConnector):
    """Database connector backed by SQLAlchemy + pandas."""

    def _build_engine(self) -> Engine:
        connection_string = str(self._require_value("connection_string"))
        return create_engine(connection_string)

    def read(self) -> pd.DataFrame:
        query = self.config.get("query")
        table = self.config.get("table")
        schema = self.config.get("schema")
        params = self.config.get("params")

        if query is None and table is None:
            raise ConnectorError(
                "Database connector read requires either 'query' or 'table' in config"
            )

        engine = self._build_engine()
        try:
            with engine.connect() as connection:
                if query is not None:
                    return pd.read_sql_query(
                        text(str(query)),
                        connection,
                        params=params,
                    )
                return pd.read_sql_table(str(table), connection, schema=schema)
        finally:
            engine.dispose()

    def write(self, data: pd.DataFrame) -> None:
        if not isinstance(data, pd.DataFrame):
            raise ConnectorError("DatabaseConnector.write expects a pandas DataFrame")

        table = self.config.get("write_table") or self.config.get("table")
        if table is None:
            raise ConnectorError(
                "Database connector write requires 'table' or 'write_table' in config"
            )

        schema = self.config.get("schema")
        if_exists = str(self.config.get("if_exists", "append"))
        include_index = bool(self.config.get("index", False))

        engine = self._build_engine()
        try:
            with engine.begin() as connection:
                data.to_sql(
                    name=str(table),
                    con=connection,
                    schema=schema,
                    if_exists=if_exists,
                    index=include_index,
                )
        finally:
            engine.dispose()
