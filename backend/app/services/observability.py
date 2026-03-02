import json
import math
import sys
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calc_cache import CalcCache
from app.models.cloudworks import CloudWorksRun, RunStatus
from app.models.collaboration import PresenceSession
from app.models.engine_profile import EngineProfile, EngineProfileMetric
from app.models.pipeline import PipelineRun, PipelineStepLog


_LATENCY_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
_RECENT_WINDOW = timedelta(minutes=5)


class ApiMetricsCollector:
    """In-process HTTP metrics collector used by middleware and dashboard endpoints."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._latency_sum_seconds = 0.0
        self._latency_count = 0
        self._in_flight_requests = 0
        self._latency_bucket_counts = {bucket: 0 for bucket in _LATENCY_BUCKETS}
        self._recent_samples: Deque[Tuple[datetime, float, bool]] = deque()

    def reset(self) -> None:
        with self._lock:
            self._requests_total = 0
            self._errors_total = 0
            self._latency_sum_seconds = 0.0
            self._latency_count = 0
            self._in_flight_requests = 0
            self._latency_bucket_counts = {bucket: 0 for bucket in _LATENCY_BUCKETS}
            self._recent_samples.clear()

    def request_started(self) -> None:
        with self._lock:
            self._in_flight_requests += 1

    def request_finished(self, latency_seconds: float, status_code: int) -> None:
        now = datetime.now(timezone.utc)
        is_error = status_code >= 400

        with self._lock:
            self._requests_total += 1
            self._latency_count += 1
            self._latency_sum_seconds += max(latency_seconds, 0.0)

            if is_error:
                self._errors_total += 1

            for bucket in _LATENCY_BUCKETS:
                if latency_seconds <= bucket:
                    self._latency_bucket_counts[bucket] += 1

            self._recent_samples.append((now, max(latency_seconds, 0.0), is_error))
            self._trim_recent_locked(now)

            if self._in_flight_requests > 0:
                self._in_flight_requests -= 1

    def _trim_recent_locked(self, now: datetime) -> None:
        cutoff = now - _RECENT_WINDOW
        while self._recent_samples and self._recent_samples[0][0] < cutoff:
            self._recent_samples.popleft()

    def snapshot(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        with self._lock:
            self._trim_recent_locked(now)

            recent_requests = len(self._recent_samples)
            recent_errors = len([sample for sample in self._recent_samples if sample[2]])
            recent_latency_sum = sum(sample[1] for sample in self._recent_samples)

            error_rate = (
                float(self._errors_total) / float(self._requests_total)
                if self._requests_total > 0
                else 0.0
            )
            avg_latency_ms = (
                (self._latency_sum_seconds / float(self._latency_count)) * 1000.0
                if self._latency_count > 0
                else 0.0
            )

            recent_error_rate = (
                float(recent_errors) / float(recent_requests)
                if recent_requests > 0
                else 0.0
            )
            recent_avg_latency_ms = (
                (recent_latency_sum / float(recent_requests)) * 1000.0
                if recent_requests > 0
                else 0.0
            )

            return {
                "requests_total": self._requests_total,
                "errors_total": self._errors_total,
                "error_rate": error_rate,
                "request_latency_ms_avg": avg_latency_ms,
                "request_latency_seconds_sum": self._latency_sum_seconds,
                "request_latency_seconds_count": self._latency_count,
                "latency_bucket_counts": dict(self._latency_bucket_counts),
                "requests_last_5m": recent_requests,
                "errors_last_5m": recent_errors,
                "error_rate_last_5m": recent_error_rate,
                "request_latency_ms_avg_last_5m": recent_avg_latency_ms,
                "in_flight_requests": self._in_flight_requests,
            }


api_metrics_collector = ApiMetricsCollector()


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _normalize_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, value))


def get_process_memory_usage_mb() -> float:
    """Return process RSS (best-effort) in MB without external dependencies."""
    try:
        import resource

        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            return rss / (1024.0 * 1024.0)
        return rss / 1024.0
    except Exception:
        return 0.0


async def count_active_users(db: AsyncSession, active_seconds: int = 60) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=active_seconds)
    result = await db.execute(
        select(func.count(func.distinct(PresenceSession.user_id))).where(
            PresenceSession.last_heartbeat >= cutoff
        )
    )
    return int(result.scalar() or 0)


async def get_engine_model_metrics(
    db: AsyncSession,
    model_id: Optional[uuid.UUID] = None,
) -> List[Dict[str, Any]]:
    profile_stmt = select(EngineProfile.id, EngineProfile.model_id)
    if model_id is not None:
        profile_stmt = profile_stmt.where(EngineProfile.model_id == model_id)

    profile_rows = list((await db.execute(profile_stmt)).all())

    if len(profile_rows) == 0:
        if model_id is None:
            return []
        return [
            {
                "model_id": model_id,
                "calc_time_ms_avg": None,
                "calc_time_ms_latest": None,
                "cache_hit_ratio": None,
                "memory_usage_mb": get_process_memory_usage_mb(),
            }
        ]

    profile_to_model: Dict[uuid.UUID, uuid.UUID] = {
        row[0]: row[1] for row in profile_rows
    }
    profile_ids = list(profile_to_model.keys())
    model_ids = list(profile_to_model.values())

    metric_rows = list(
        (
            await db.execute(
                select(
                    EngineProfileMetric.profile_id,
                    EngineProfileMetric.metric_name,
                    EngineProfileMetric.metric_value,
                    EngineProfileMetric.measured_at,
                )
                .where(
                    EngineProfileMetric.profile_id.in_(profile_ids),
                    EngineProfileMetric.metric_name.in_(
                        [
                            "calc_time_ms",
                            "memory_usage_mb",
                            "cache_hit_ratio",
                            "cache_hits",
                            "cache_misses",
                        ]
                    ),
                )
                .order_by(EngineProfileMetric.measured_at.desc())
            )
        ).all()
    )

    calc_values_by_profile: Dict[uuid.UUID, List[float]] = {}
    latest_metric_by_profile: Dict[uuid.UUID, Dict[str, float]] = {}
    cache_hits_by_profile: Dict[uuid.UUID, float] = {}
    cache_misses_by_profile: Dict[uuid.UUID, float] = {}

    for row in metric_rows:
        profile_id = row[0]
        metric_name = row[1]
        metric_value = float(row[2])

        if profile_id not in latest_metric_by_profile:
            latest_metric_by_profile[profile_id] = {}

        if metric_name not in latest_metric_by_profile[profile_id]:
            latest_metric_by_profile[profile_id][metric_name] = metric_value

        if metric_name == "calc_time_ms":
            calc_values_by_profile.setdefault(profile_id, []).append(metric_value)
        elif metric_name == "cache_hits":
            cache_hits_by_profile[profile_id] = (
                cache_hits_by_profile.get(profile_id, 0.0) + metric_value
            )
        elif metric_name == "cache_misses":
            cache_misses_by_profile[profile_id] = (
                cache_misses_by_profile.get(profile_id, 0.0) + metric_value
            )

    cache_fallback_rows = list(
        (
            await db.execute(
                select(
                    CalcCache.model_id,
                    func.count(CalcCache.id),
                    func.sum(case((CalcCache.is_valid == True, 1), else_=0)),  # noqa: E712
                )
                .where(CalcCache.model_id.in_(model_ids))
                .group_by(CalcCache.model_id)
            )
        ).all()
    )
    cache_ratio_by_model: Dict[uuid.UUID, float] = {}
    for row in cache_fallback_rows:
        cached_model_id = row[0]
        total_count = int(row[1] or 0)
        valid_count = int(row[2] or 0)
        cache_ratio_by_model[cached_model_id] = _safe_divide(
            float(valid_count), float(total_count)
        )

    process_memory_mb = get_process_memory_usage_mb()

    metrics: List[Dict[str, Any]] = []
    for profile_id, current_model_id in profile_to_model.items():
        latest = latest_metric_by_profile.get(profile_id, {})
        calc_values = calc_values_by_profile.get(profile_id, [])

        calc_avg = (
            sum(calc_values) / float(len(calc_values))
            if len(calc_values) > 0
            else None
        )
        calc_latest = latest.get("calc_time_ms")
        memory_usage_mb = latest.get("memory_usage_mb", process_memory_mb)

        cache_ratio = _normalize_ratio(latest.get("cache_hit_ratio"))
        if cache_ratio is None:
            cache_hits = cache_hits_by_profile.get(profile_id, 0.0)
            cache_misses = cache_misses_by_profile.get(profile_id, 0.0)
            if (cache_hits + cache_misses) > 0:
                cache_ratio = _normalize_ratio(
                    _safe_divide(cache_hits, cache_hits + cache_misses)
                )
            else:
                cache_ratio = _normalize_ratio(cache_ratio_by_model.get(current_model_id))

        metrics.append(
            {
                "model_id": current_model_id,
                "calc_time_ms_avg": calc_avg,
                "calc_time_ms_latest": calc_latest,
                "cache_hit_ratio": cache_ratio,
                "memory_usage_mb": memory_usage_mb,
            }
        )

    metrics.sort(key=lambda item: str(item["model_id"]))
    return metrics


async def get_integration_metrics(db: AsyncSession) -> Dict[str, Any]:
    cloudworks_rows = list(
        (
            await db.execute(
                select(CloudWorksRun.status, func.count(CloudWorksRun.id)).group_by(
                    CloudWorksRun.status
                )
            )
        ).all()
    )

    cloudworks_count_by_status: Dict[str, int] = {}
    for row in cloudworks_rows:
        status_name = row[0].value if isinstance(row[0], RunStatus) else str(row[0])
        cloudworks_count_by_status[status_name] = int(row[1] or 0)

    cloudworks_runs_total = int(sum(cloudworks_count_by_status.values()))
    cloudworks_completed = int(cloudworks_count_by_status.get(RunStatus.completed.value, 0))
    cloudworks_failed = int(cloudworks_count_by_status.get(RunStatus.failed.value, 0))
    cloudworks_success_rate = _safe_divide(
        float(cloudworks_completed),
        float(cloudworks_completed + cloudworks_failed),
    )

    pipeline_runs_total_result = await db.execute(select(func.count(PipelineRun.id)))
    pipeline_runs_total = int(pipeline_runs_total_result.scalar() or 0)

    throughput_result = await db.execute(
        select(
            func.coalesce(func.sum(PipelineStepLog.records_out), 0),
            func.min(PipelineStepLog.started_at),
            func.max(PipelineStepLog.completed_at),
        ).where(
            PipelineStepLog.records_out.is_not(None),
            PipelineStepLog.started_at.is_not(None),
            PipelineStepLog.completed_at.is_not(None),
        )
    )
    throughput_row = throughput_result.one()
    throughput_records = float(throughput_row[0] or 0)
    earliest_started_at = throughput_row[1]
    latest_completed_at = throughput_row[2]

    throughput_per_minute = 0.0
    if earliest_started_at is not None and latest_completed_at is not None:
        window_seconds = (latest_completed_at - earliest_started_at).total_seconds()
        if window_seconds <= 0:
            window_seconds = 60.0
        throughput_per_minute = throughput_records / (window_seconds / 60.0)

    return {
        "cloudworks_runs_total": cloudworks_runs_total,
        "cloudworks_run_success_rate": cloudworks_success_rate,
        "pipeline_runs_total": pipeline_runs_total,
        "pipeline_throughput_records_per_minute": throughput_per_minute,
    }


async def build_health_checks(
    db: AsyncSession,
    api_error_rate_last_5m: float,
    cloudworks_runs_total: int,
    cloudworks_run_success_rate: float,
) -> Tuple[str, List[Dict[str, str]]]:
    checks: List[Dict[str, str]] = []

    db_status = "ok"
    db_detail = "Database reachable"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = "degraded"
        db_detail = "Database health check failed: %s" % str(exc)

    checks.append(
        {
            "name": "database",
            "status": db_status,
            "detail": db_detail,
        }
    )

    api_status = "ok"
    api_detail = "API error rate over last 5 minutes is %.2f%%" % (api_error_rate_last_5m * 100.0)
    if api_error_rate_last_5m > 0.1:
        api_status = "degraded"
        api_detail = "API error rate over last 5 minutes is high: %.2f%%" % (
            api_error_rate_last_5m * 100.0
        )

    checks.append(
        {
            "name": "api_error_rate",
            "status": api_status,
            "detail": api_detail,
        }
    )

    cloudworks_status = "ok"
    if cloudworks_runs_total == 0:
        cloudworks_detail = "No CloudWorks runs recorded yet"
    else:
        cloudworks_detail = "CloudWorks run success rate is %.2f%%" % (
            cloudworks_run_success_rate * 100.0
        )
        if cloudworks_run_success_rate < 0.9:
            cloudworks_status = "degraded"
            cloudworks_detail = "CloudWorks run success rate is below target: %.2f%%" % (
                cloudworks_run_success_rate * 100.0
            )

    checks.append(
        {
            "name": "cloudworks_success_rate",
            "status": cloudworks_status,
            "detail": cloudworks_detail,
        }
    )

    overall_status = "ok"
    if any(check["status"] != "ok" for check in checks):
        overall_status = "degraded"

    return overall_status, checks


async def build_observability_dashboard(
    db: AsyncSession,
    model_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    api_snapshot = api_metrics_collector.snapshot()
    active_users = await count_active_users(db)
    engine_models = await get_engine_model_metrics(db, model_id=model_id)
    integration = await get_integration_metrics(db)

    health_status, checks = await build_health_checks(
        db,
        api_error_rate_last_5m=api_snapshot["error_rate_last_5m"],
        cloudworks_runs_total=integration["cloudworks_runs_total"],
        cloudworks_run_success_rate=integration["cloudworks_run_success_rate"],
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "engine": {
            "tracked_models": len(engine_models),
            "models": engine_models,
        },
        "api": {
            "request_latency_ms_avg": api_snapshot["request_latency_ms_avg"],
            "request_latency_ms_avg_last_5m": api_snapshot[
                "request_latency_ms_avg_last_5m"
            ],
            "error_rate": api_snapshot["error_rate"],
            "error_rate_last_5m": api_snapshot["error_rate_last_5m"],
            "requests_total": api_snapshot["requests_total"],
            "requests_last_5m": api_snapshot["requests_last_5m"],
            "in_flight_requests": api_snapshot["in_flight_requests"],
            "active_users": active_users,
        },
        "integration": integration,
        "health_status": health_status,
        "checks": checks,
    }


_GRAFANA_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "monitoring"
    / "grafana"
    / "dynaplan-observability-dashboard.json"
)


def get_grafana_dashboard_template() -> Dict[str, Any]:
    try:
        with _GRAFANA_TEMPLATE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {
            "title": "Dynaplan Observability",
            "description": "Fallback Grafana dashboard template",
            "panels": [],
        }


def _format_prometheus_value(value: Optional[float]) -> str:
    if value is None:
        return "0"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "0"
    return ("%.12f" % float(value)).rstrip("0").rstrip(".") or "0"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def render_prometheus_metrics(db: AsyncSession) -> str:
    api_snapshot = api_metrics_collector.snapshot()
    active_users = await count_active_users(db)
    engine_models = await get_engine_model_metrics(db)
    integration = await get_integration_metrics(db)
    health_status, _ = await build_health_checks(
        db,
        api_error_rate_last_5m=api_snapshot["error_rate_last_5m"],
        cloudworks_runs_total=integration["cloudworks_runs_total"],
        cloudworks_run_success_rate=integration["cloudworks_run_success_rate"],
    )

    lines: List[str] = []

    lines.append("# HELP dynaplan_api_requests_total Total HTTP requests observed by Dynaplan API")
    lines.append("# TYPE dynaplan_api_requests_total counter")
    lines.append("dynaplan_api_requests_total %d" % int(api_snapshot["requests_total"]))

    lines.append("# HELP dynaplan_api_errors_total Total HTTP error responses observed by Dynaplan API")
    lines.append("# TYPE dynaplan_api_errors_total counter")
    lines.append("dynaplan_api_errors_total %d" % int(api_snapshot["errors_total"]))

    lines.append("# HELP dynaplan_api_request_latency_seconds Request latency histogram")
    lines.append("# TYPE dynaplan_api_request_latency_seconds histogram")
    for bucket in _LATENCY_BUCKETS:
        bucket_count = int(api_snapshot["latency_bucket_counts"].get(bucket, 0))
        lines.append(
            'dynaplan_api_request_latency_seconds_bucket{le="%s"} %d'
            % (_format_prometheus_value(bucket), bucket_count)
        )
    lines.append(
        'dynaplan_api_request_latency_seconds_bucket{le="+Inf"} %d'
        % int(api_snapshot["requests_total"])
    )
    lines.append(
        "dynaplan_api_request_latency_seconds_sum %s"
        % _format_prometheus_value(api_snapshot["request_latency_seconds_sum"])
    )
    lines.append(
        "dynaplan_api_request_latency_seconds_count %d"
        % int(api_snapshot["request_latency_seconds_count"])
    )

    lines.append("# HELP dynaplan_api_in_flight_requests Current number of in-flight HTTP requests")
    lines.append("# TYPE dynaplan_api_in_flight_requests gauge")
    lines.append("dynaplan_api_in_flight_requests %d" % int(api_snapshot["in_flight_requests"]))

    lines.append("# HELP dynaplan_api_active_users Current active users across models")
    lines.append("# TYPE dynaplan_api_active_users gauge")
    lines.append("dynaplan_api_active_users %d" % int(active_users))

    lines.append("# HELP dynaplan_engine_calc_time_ms_avg Average model calculation time in milliseconds")
    lines.append("# TYPE dynaplan_engine_calc_time_ms_avg gauge")
    for model_metrics in engine_models:
        label_model_id = _escape_label_value(str(model_metrics["model_id"]))
        lines.append(
            'dynaplan_engine_calc_time_ms_avg{model_id="%s"} %s'
            % (label_model_id, _format_prometheus_value(model_metrics["calc_time_ms_avg"]))
        )

    lines.append("# HELP dynaplan_engine_cache_hit_ratio Cache hit ratio per model")
    lines.append("# TYPE dynaplan_engine_cache_hit_ratio gauge")
    for model_metrics in engine_models:
        label_model_id = _escape_label_value(str(model_metrics["model_id"]))
        lines.append(
            'dynaplan_engine_cache_hit_ratio{model_id="%s"} %s'
            % (label_model_id, _format_prometheus_value(model_metrics["cache_hit_ratio"]))
        )

    lines.append("# HELP dynaplan_engine_memory_usage_mb Engine memory usage in MB")
    lines.append("# TYPE dynaplan_engine_memory_usage_mb gauge")
    for model_metrics in engine_models:
        label_model_id = _escape_label_value(str(model_metrics["model_id"]))
        lines.append(
            'dynaplan_engine_memory_usage_mb{model_id="%s"} %s'
            % (label_model_id, _format_prometheus_value(model_metrics["memory_usage_mb"]))
        )

    lines.append("# HELP dynaplan_cloudworks_run_success_rate CloudWorks run success rate")
    lines.append("# TYPE dynaplan_cloudworks_run_success_rate gauge")
    lines.append(
        "dynaplan_cloudworks_run_success_rate %s"
        % _format_prometheus_value(integration["cloudworks_run_success_rate"])
    )

    lines.append("# HELP dynaplan_pipeline_throughput_records_per_minute Pipeline throughput in records per minute")
    lines.append("# TYPE dynaplan_pipeline_throughput_records_per_minute gauge")
    lines.append(
        "dynaplan_pipeline_throughput_records_per_minute %s"
        % _format_prometheus_value(
            integration["pipeline_throughput_records_per_minute"]
        )
    )

    lines.append("# HELP dynaplan_health_status Overall application health status (1=ok, 0=degraded)")
    lines.append("# TYPE dynaplan_health_status gauge")
    lines.append("dynaplan_health_status %d" % (1 if health_status == "ok" else 0))

    return "\n".join(lines) + "\n"
