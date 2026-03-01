import enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ExportFormat(str, enum.Enum):
    csv = "csv"
    xlsx = "xlsx"


class ImportPreview(BaseModel):
    column_names: List[str]
    sample_rows: List[Dict[str, Any]]
    suggested_mapping: Dict[str, Optional[str]]


class ImportResult(BaseModel):
    rows_imported: int
    rows_skipped: int
    errors: List[str]
