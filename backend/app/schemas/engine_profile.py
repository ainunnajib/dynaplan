import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# EngineProfile
# ---------------------------------------------------------------------------


class EngineProfileCreate(BaseModel):
    profile_type: str  # "classic" or "polaris"
    max_cells: int = 10_000_000
    max_dimensions: int = 20
    max_line_items: int = 1000
    sparse_optimization: bool = False
    parallel_calc: bool = False
    memory_limit_mb: int = 4096
    settings: Optional[dict] = None


class EngineProfileUpdate(BaseModel):
    profile_type: Optional[str] = None
    max_cells: Optional[int] = None
    max_dimensions: Optional[int] = None
    max_line_items: Optional[int] = None
    sparse_optimization: Optional[bool] = None
    parallel_calc: Optional[bool] = None
    memory_limit_mb: Optional[int] = None
    settings: Optional[dict] = None


class EngineProfileResponse(BaseModel):
    id: uuid.UUID
    model_id: uuid.UUID
    profile_type: str
    max_cells: int
    max_dimensions: int
    max_line_items: int
    sparse_optimization: bool
    parallel_calc: bool
    memory_limit_mb: int
    settings: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# EngineProfileMetric
# ---------------------------------------------------------------------------


class MetricCreate(BaseModel):
    metric_name: str
    metric_value: float
    metadata: Optional[dict] = None


class MetricResponse(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    metric_name: str
    metric_value: float
    measured_at: datetime
    metadata_json: Optional[dict]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ModelDesignGuidance
# ---------------------------------------------------------------------------


class GuidanceCreate(BaseModel):
    profile_type: str  # "classic" or "polaris"
    rule_code: str
    severity: str  # "info", "warning", "error"
    title: str
    description: str
    threshold_value: Optional[float] = None


class GuidanceResponse(BaseModel):
    id: uuid.UUID
    profile_type: str
    rule_code: str
    severity: str
    title: str
    description: str
    threshold_value: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Evaluation & Recommendation
# ---------------------------------------------------------------------------


class RuleViolation(BaseModel):
    rule_code: str
    severity: str
    title: str
    description: str
    threshold_value: Optional[float]
    actual_value: Optional[float]


class ModelEvaluationResult(BaseModel):
    model_id: uuid.UUID
    profile_type: str
    violations: List[RuleViolation]
    passed: bool


class ProfileRecommendation(BaseModel):
    model_id: uuid.UUID
    recommended_profile: str
    reason: str
    estimated_cells: int
    dimension_count: int
    sparsity_ratio: float
