"""Health Endpoint for Sahaay Core Backend."""

import asyncio
import sys
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from sahaay_core.config.settings import settings
from sahaay_core.storage.persistence import durable_storage

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    systemVersion: str
    pythonVersion: str
    localOnlyMode: bool
    timestamp: datetime
    databaseReady: bool
    subsystems: dict = {}


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return system operational status and runtime diagnostics with multi-layer health."""
    db_ok = await asyncio.to_thread(durable_storage.verify_connection)

    from sahaay_core.adapters.browser.adapter import BrowserAdapter
    from sahaay_core.adapters.windows.adapter import WindowsNativeAdapter
    from sahaay_core.capabilities.registry import capability_registry
    from sahaay_core.models.meta.meta_client import MetaClient
    from sahaay_core.skills.manager import skills_manager

    win_adapter = WindowsNativeAdapter(allow_simulation=False)
    br_adapter = BrowserAdapter(allow_simulation=False)
    meta_client = MetaClient()

    subsystems = {
        "fastapiCore": {"status": "ONLINE", "host": settings.host, "port": settings.port},
        "taskWorker": {"status": "READY", "storage": "sqlite_wal"},
        "metaProvider": {
            "status": "CONFIGURED" if meta_client.is_configured else "UNCONFIGURED",
            "model": "muse-spark-1.3",
        },
        "browserExtension": {
            "status": "CONNECTED" if br_adapter.is_connected() else "STANDBY",
            "attached": br_adapter.is_browser_attached() if br_adapter.is_connected() else False,
        },
        "windowsController": {
            "status": "CONNECTED" if win_adapter.is_connected() else "STOPPED",
            "pipe": "\\\\.\\pipe\\SahaayControllerPipe",
        },
        "documentDataServices": {"status": "READY", "engine": "sqlite_in_memory_openxml"},
        "skillsCatalog": {"status": "READY", "loadedCount": len(skills_manager.list_skills())},
        "capabilitiesCatalog": {"status": "READY", "totalRegistered": len(capability_registry.list_capabilities())},
    }

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        systemVersion="0.2.0-general-agent",
        pythonVersion=sys.version.split(" ")[0],
        localOnlyMode=settings.local_only_mode,
        timestamp=datetime.now(timezone.utc),
        databaseReady=db_ok,
        subsystems=subsystems,
    )
