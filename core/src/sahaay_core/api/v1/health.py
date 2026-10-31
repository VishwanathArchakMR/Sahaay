"""Health Endpoint for Sahaay Core Backend."""

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


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return system operational status and runtime diagnostics."""
    db_ok = durable_storage.verify_connection()
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        systemVersion="0.1.0-foundation",
        pythonVersion=sys.version.split(" ")[0],
        localOnlyMode=settings.local_only_mode,
        timestamp=datetime.now(timezone.utc),
        databaseReady=db_ok,
    )
