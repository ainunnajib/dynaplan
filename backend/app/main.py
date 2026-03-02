import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.action import router as action_router
from app.api.audit import router as audit_router
from app.api.collaboration import router as collaboration_router
from app.api.rbac import router as rbac_router
from app.api.calc_cache import router as calc_cache_router
from app.api.comment import router as comment_router
from app.api.composite_dimension import router as composite_dimension_router
from app.api.planning import router as planning_router
from app.api.rolling_forecast import router as rolling_forecast_router
from app.api.api_keys import router as api_keys_router
from app.api.auth import router as auth_router
from app.api.cell import router as cell_router
from app.api.dashboard import router as dashboard_router
from app.api.dashboard_share import router as dashboard_share_router
from app.api.dimension import router as dimension_router
from app.api.import_export import router as import_export_router
from app.api.module import router as module_router
from app.api.planning_model import router as planning_model_router
from app.api.public_api import router as public_api_router
from app.api.scenario_compare import router as scenario_compare_router
from app.api.whatif import router as whatif_router
from app.api.bulk_ops import router as bulk_ops_router
from app.api.snapshot import router as snapshot_router
from app.api.sso import router as sso_router
from app.api.time_range import router as time_range_router
from app.api.subset import router as subset_router
from app.api.dca import router as dca_router
from app.api.ux_page import router as ux_page_router
from app.api.report import router as report_router
from app.api.workflow import router as workflow_router
from app.api.chunked_upload import router as chunked_upload_router
from app.api.engine_profile import router as engine_profile_router
from app.api.alm import router as alm_router
from app.api.cloudworks import router as cloudworks_router
from app.api.pipeline import router as pipeline_router
from app.api.scim import router as scim_router
from app.api.saved_view import router as saved_view_router
from app.api.data_hub import router as data_hub_router
from app.api.model_encryption import router as model_encryption_router
from app.api.time_dimension import router as time_dimension_router
from app.api.version import router as version_router
from app.api.workspace import router as workspace_router
from app.api.workspace_quota import router as workspace_quota_router
from app.core.config import settings
from app.core.database import dispose_engines, engine
from app.models import Base
from app.services.cloudworks import shutdown_cloudworks_runtime, start_cloudworks_runtime

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dynaplan",
    description="Enterprise planning platform - open-source Anaplan alternative",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(workspace_quota_router)
app.include_router(planning_model_router)
app.include_router(dimension_router)
app.include_router(composite_dimension_router)
app.include_router(module_router)
app.include_router(cell_router)
app.include_router(time_dimension_router)
app.include_router(version_router)
app.include_router(dashboard_share_router)
app.include_router(dashboard_router)
app.include_router(import_export_router)
app.include_router(api_keys_router)
app.include_router(public_api_router)
app.include_router(action_router)
app.include_router(comment_router)
app.include_router(planning_router)
app.include_router(rolling_forecast_router)
app.include_router(scenario_compare_router)
app.include_router(whatif_router)
app.include_router(rbac_router)
app.include_router(calc_cache_router)
app.include_router(collaboration_router)
app.include_router(bulk_ops_router)
app.include_router(snapshot_router)
app.include_router(audit_router)
app.include_router(sso_router)
app.include_router(time_range_router)
app.include_router(subset_router)
app.include_router(dca_router)
app.include_router(ux_page_router)
app.include_router(report_router)
app.include_router(workflow_router)
app.include_router(engine_profile_router)
app.include_router(chunked_upload_router)
app.include_router(alm_router)
app.include_router(cloudworks_router)
app.include_router(pipeline_router)
app.include_router(scim_router)
app.include_router(saved_view_router)
app.include_router(data_hub_router)
app.include_router(model_encryption_router)


async def _ensure_schema_compatibility(conn) -> None:
    """Patch additive columns that may be missing in long-lived databases."""
    dialect = conn.dialect.name

    if dialect == "postgresql":
        await conn.exec_driver_sql(
            "ALTER TABLE dimensions ADD COLUMN IF NOT EXISTS max_items INTEGER"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE cell_values ADD COLUMN IF NOT EXISTS value_encrypted TEXT"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE cell_values ADD COLUMN IF NOT EXISTS encryption_key_id UUID"
        )
        await conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_cell_values_encryption_key_id "
            "ON cell_values (encryption_key_id)"
        )
        return

    if dialect == "sqlite":
        info = await conn.exec_driver_sql("PRAGMA table_info(dimensions)")
        columns = {row[1] for row in info.fetchall()}
        if "max_items" not in columns:
            await conn.exec_driver_sql(
                "ALTER TABLE dimensions ADD COLUMN max_items INTEGER"
            )

        cell_info = await conn.exec_driver_sql("PRAGMA table_info(cell_values)")
        cell_columns = {row[1] for row in cell_info.fetchall()}
        if "value_encrypted" not in cell_columns:
            await conn.exec_driver_sql(
                "ALTER TABLE cell_values ADD COLUMN value_encrypted TEXT"
            )
        if "encryption_key_id" not in cell_columns:
            await conn.exec_driver_sql(
                "ALTER TABLE cell_values ADD COLUMN encryption_key_id CHAR(32)"
            )


@app.on_event("startup")
async def startup_init_schema():
    if settings.auto_create_schema:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _ensure_schema_compatibility(conn)

    try:
        await start_cloudworks_runtime()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to start CloudWorks scheduler runtime")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@app.on_event("shutdown")
async def shutdown_dispose_all_engines():
    try:
        await shutdown_cloudworks_runtime()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to shut down CloudWorks scheduler runtime")
    await dispose_engines()
