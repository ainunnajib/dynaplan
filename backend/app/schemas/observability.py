import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EngineModelMetrics(BaseModel):
    model_id: uuid.UUID
    calc_time_ms_avg: Optional[float] = None
    calc_time_ms_latest: Optional[float] = None
    cache_hit_ratio: Optional[float] = None
    memory_usage_mb: Optional[float] = None


class EngineMetricsSection(BaseModel):
    tracked_models: int
    models: List[EngineModelMetrics]


class ApiMetricsSection(BaseModel):
    request_latency_ms_avg: float
    request_latency_ms_avg_last_5m: float
    error_rate: float
    error_rate_last_5m: float
    requests_total: int
    requests_last_5m: int
    in_flight_requests: int
    active_users: int


class IntegrationMetricsSection(BaseModel):
    cloudworks_runs_total: int
    cloudworks_run_success_rate: float
    pipeline_runs_total: int
    pipeline_throughput_records_per_minute: float


class HealthCheckItem(BaseModel):
    name: str
    status: str
    detail: str


class ObservabilityDashboardResponse(BaseModel):
    generated_at: datetime
    engine: EngineMetricsSection
    api: ApiMetricsSection
    integration: IntegrationMetricsSection
    health_status: str
    checks: List[HealthCheckItem]


class GrafanaDashboardTemplateResponse(BaseModel):
    title: str
    template: Dict[str, Any]
