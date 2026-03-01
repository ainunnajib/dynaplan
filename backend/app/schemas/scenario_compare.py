"""Pydantic schemas for F024: Scenario comparison."""
from typing import Dict, List, Optional

from pydantic import BaseModel


class ComparisonRequest(BaseModel):
    """Request body for comparing multiple versions."""
    version_ids: List[str]
    line_item_ids: Optional[List[str]] = None
    dimension_filters: Optional[Dict[str, List[str]]] = None


class ComparisonRow(BaseModel):
    """A single row in the comparison result, representing one line item + dimension_key intersection."""
    line_item_id: str
    line_item_name: str
    dimension_key: str
    # Maps version_id (str) -> value (float or None)
    values: Dict[str, Optional[float]]
    # Difference between last and first version (only computed when exactly 2 versions)
    absolute_diff: Optional[float]
    percentage_diff: Optional[float]


class ComparisonResponse(BaseModel):
    """Response for a version comparison."""
    rows: List[ComparisonRow]
    # Maps version_id (str) -> version name
    version_names: Dict[str, str]


class VarianceSummaryRequest(BaseModel):
    """Request body for variance summary between exactly two versions."""
    base_version_id: str
    compare_version_id: str
    line_item_ids: Optional[List[str]] = None


class VarianceSummary(BaseModel):
    """Aggregate variance statistics between two versions."""
    total_absolute_diff: float
    avg_percentage_diff: Optional[float]
    changed_cells: int
    unchanged_cells: int
    total_cells: int


class MatrixRequest(BaseModel):
    """Request body for comparison matrix for a single line item."""
    version_ids: List[str]
    line_item_id: str


class MatrixCell(BaseModel):
    """A single cell in the comparison matrix."""
    version_id: str
    version_name: str
    dimension_key: str
    value: Optional[float]


class ComparisonMatrix(BaseModel):
    """Matrix of cell values for a single line item across multiple versions."""
    line_item_id: str
    version_names: Dict[str, str]
    # dimension_key -> {version_id -> value}
    matrix: Dict[str, Dict[str, Optional[float]]]
    dimension_keys: List[str]
