import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engine_profile import (
    EngineProfile,
    EngineProfileMetric,
    GuidanceSeverity,
    ModelDesignGuidance,
    ProfileType,
)
from app.schemas.engine_profile import (
    EngineProfileCreate,
    EngineProfileUpdate,
    GuidanceCreate,
    MetricCreate,
    ModelEvaluationResult,
    ProfileRecommendation,
    RuleViolation,
)


# ---------------------------------------------------------------------------
# Engine profile CRUD (one per model, upsert)
# ---------------------------------------------------------------------------


async def upsert_engine_profile(
    db: AsyncSession,
    model_id: uuid.UUID,
    data: EngineProfileCreate,
) -> EngineProfile:
    result = await db.execute(
        select(EngineProfile).where(EngineProfile.model_id == model_id)
    )
    profile = result.scalar_one_or_none()

    if profile is not None:
        profile.profile_type = ProfileType(data.profile_type)
        profile.max_cells = data.max_cells
        profile.max_dimensions = data.max_dimensions
        profile.max_line_items = data.max_line_items
        profile.sparse_optimization = data.sparse_optimization
        profile.parallel_calc = data.parallel_calc
        profile.memory_limit_mb = data.memory_limit_mb
        if data.settings is not None:
            profile.settings = data.settings
    else:
        profile = EngineProfile(
            model_id=model_id,
            profile_type=ProfileType(data.profile_type),
            max_cells=data.max_cells,
            max_dimensions=data.max_dimensions,
            max_line_items=data.max_line_items,
            sparse_optimization=data.sparse_optimization,
            parallel_calc=data.parallel_calc,
            memory_limit_mb=data.memory_limit_mb,
            settings=data.settings,
        )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_engine_profile(
    db: AsyncSession, model_id: uuid.UUID
) -> Optional[EngineProfile]:
    result = await db.execute(
        select(EngineProfile).where(EngineProfile.model_id == model_id)
    )
    return result.scalar_one_or_none()


async def delete_engine_profile(
    db: AsyncSession, profile: EngineProfile
) -> None:
    await db.delete(profile)
    await db.commit()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


async def record_metric(
    db: AsyncSession,
    profile_id: uuid.UUID,
    data: MetricCreate,
) -> EngineProfileMetric:
    metric = EngineProfileMetric(
        profile_id=profile_id,
        metric_name=data.metric_name,
        metric_value=data.metric_value,
        metadata_json=data.metadata,
    )
    db.add(metric)
    await db.commit()
    await db.refresh(metric)
    return metric


async def list_metrics(
    db: AsyncSession, profile_id: uuid.UUID
) -> List[EngineProfileMetric]:
    result = await db.execute(
        select(EngineProfileMetric)
        .where(EngineProfileMetric.profile_id == profile_id)
        .order_by(EngineProfileMetric.measured_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Guidance rules CRUD
# ---------------------------------------------------------------------------


async def create_guidance(
    db: AsyncSession, data: GuidanceCreate
) -> ModelDesignGuidance:
    rule = ModelDesignGuidance(
        profile_type=ProfileType(data.profile_type),
        rule_code=data.rule_code,
        severity=GuidanceSeverity(data.severity),
        title=data.title,
        description=data.description,
        threshold_value=data.threshold_value,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_guidance(
    db: AsyncSession, profile_type: Optional[str] = None
) -> List[ModelDesignGuidance]:
    stmt = select(ModelDesignGuidance).order_by(ModelDesignGuidance.created_at.asc())
    if profile_type is not None:
        stmt = stmt.where(
            ModelDesignGuidance.profile_type == ProfileType(profile_type)
        )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_guidance_by_id(
    db: AsyncSession, rule_id: uuid.UUID
) -> Optional[ModelDesignGuidance]:
    result = await db.execute(
        select(ModelDesignGuidance).where(ModelDesignGuidance.id == rule_id)
    )
    return result.scalar_one_or_none()


async def delete_guidance(
    db: AsyncSession, rule: ModelDesignGuidance
) -> None:
    await db.delete(rule)
    await db.commit()


# ---------------------------------------------------------------------------
# Evaluate model against guidance
# ---------------------------------------------------------------------------


async def evaluate_model(
    db: AsyncSession,
    model_id: uuid.UUID,
    profile: EngineProfile,
    dimension_count: int = 0,
    cell_estimate: int = 0,
    line_item_count: int = 0,
) -> ModelEvaluationResult:
    rules = await list_guidance(db, profile.profile_type.value)
    violations: List[RuleViolation] = []

    stats = {
        "max_dimensions": dimension_count,
        "max_cells": cell_estimate,
        "max_line_items": line_item_count,
    }

    for rule in rules:
        if rule.threshold_value is None:
            continue
        # Match rule_code prefix to stats key
        actual_value = None
        if "dimension" in rule.rule_code:
            actual_value = float(stats.get("max_dimensions", 0))
        elif "cell" in rule.rule_code:
            actual_value = float(stats.get("max_cells", 0))
        elif "line_item" in rule.rule_code:
            actual_value = float(stats.get("max_line_items", 0))

        if actual_value is not None and actual_value > rule.threshold_value:
            violations.append(
                RuleViolation(
                    rule_code=rule.rule_code,
                    severity=rule.severity.value,
                    title=rule.title,
                    description=rule.description,
                    threshold_value=rule.threshold_value,
                    actual_value=actual_value,
                )
            )

    return ModelEvaluationResult(
        model_id=model_id,
        profile_type=profile.profile_type.value,
        violations=violations,
        passed=len(violations) == 0,
    )


# ---------------------------------------------------------------------------
# Profile recommendation
# ---------------------------------------------------------------------------


async def recommend_profile(
    db: AsyncSession,
    model_id: uuid.UUID,
    dimension_count: int = 0,
    cell_estimate: int = 0,
    sparsity_ratio: float = 0.0,
) -> ProfileRecommendation:
    # Polaris is recommended for sparse, high-cardinality models
    if (
        dimension_count > 10
        or cell_estimate > 50_000_000
        or sparsity_ratio > 0.5
    ):
        recommended = "polaris"
        reason = (
            "Model has high dimensionality, large cell count, or high sparsity "
            "making Polaris engine more efficient."
        )
    else:
        recommended = "classic"
        reason = (
            "Model characteristics fit within Classic engine boundaries for "
            "optimal performance."
        )

    return ProfileRecommendation(
        model_id=model_id,
        recommended_profile=recommended,
        reason=reason,
        estimated_cells=cell_estimate,
        dimension_count=dimension_count,
        sparsity_ratio=sparsity_ratio,
    )
