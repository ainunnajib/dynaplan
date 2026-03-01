from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.action import router as action_router
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
from app.api.time_dimension import router as time_dimension_router
from app.api.version import router as version_router
from app.api.workspace import router as workspace_router
from app.core.config import settings

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
app.include_router(planning_model_router)
app.include_router(dimension_router)
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


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
