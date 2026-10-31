"""Sahaay Core Backend Main Application."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sahaay_core.api.v1.actions import router as actions_router
from sahaay_core.api.v1.audit import router as audit_router
from sahaay_core.api.v1.browser import router as browser_router
from sahaay_core.api.v1.capabilities import router as capabilities_router
from sahaay_core.api.v1.health import router as health_router
from sahaay_core.api.v1.models import router as models_router
from sahaay_core.api.v1.research import router as research_router
from sahaay_core.api.v1.sessions import router as sessions_router
from sahaay_core.api.v1.sources import router as sources_router
from sahaay_core.api.v1.storytelling import storytelling_router
from sahaay_core.api.v1.tasks import router as tasks_router
from sahaay_core.api.v1.windows import router as windows_router
from sahaay_core.api.v1.workflows import router as workflows_router
from sahaay_core.config.logging import logger
from sahaay_core.config.settings import settings
from sahaay_core.storage.database import init_db
from sahaay_core.storage.persistence import durable_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle hooks: initialize database and verify configuration."""
    logger.info("Initializing Sahaay Core Backend (Stage 01 Foundation)...")
    logger.info(f"Local-only mode: {settings.local_only_mode}")
    logger.info(f"Listening address: {settings.host}:{settings.port}")
    await init_db()
    reconciled = durable_storage.reconcile_stale_tasks()
    if reconciled:
        logger.info(f"Reconciled {reconciled} orphaned in-progress task(s) to FAILED/UNVERIFIED.")
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Sahaay Core Backend.")


app = FastAPI(
    title="Sahaay Core Backend",
    version="0.1.0",
    description="Authoritative backend orchestrator for Sahaay Desktop AI Agent",
    lifespan=lifespan,
)

# CORS: strictly allow loopback desktop & installed Sahaay extension origins
EXPLICIT_EXTENSION_ORIGINS = [
    "chrome-extension://filgbgddapmjcddcoadfpimdicmkhpolc",
    "extension://filgbgddapmjcddcoadfpimdicmkhpolc",
    "chrome-extension://nokchmadkhaghgooijgkgpheoieaibdp",
    "extension://nokchmadkhaghgooijgkgpheoieaibdp",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:5173",
        "http://localhost:3000",
        *EXPLICIT_EXTENSION_ORIGINS,
    ],
    allow_origin_regex=r"^(chrome-extension|extension)://[a-p]{32}$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_token_middleware(request: Request, call_next):
    """Enforce token authentication on internal API routes.

    CORS OPTIONS preflight and Health endpoint are public for startup probing;
    all others require valid X-Sahaay-Token.
    """
    path = request.url.path
    if (
        request.method == "OPTIONS"
        or path in ("/api/v1/health", "/docs", "/openapi.json")
        or path.startswith("/fixtures")
        or path.startswith("/artifacts")
    ):
        return await call_next(request)

    token = request.headers.get("X-Sahaay-Token")
    client_host = request.client.host if request.client else ""
    origin = request.headers.get("Origin", "")
    is_loopback_or_extension = (
        client_host in ("127.0.0.1", "localhost", "testclient")
        or any(
            origin.startswith(prefix)
            for prefix in (
                "chrome-extension://",
                "extension://",
                "http://localhost",
                "http://127.0.0.1",
            )
        )
    )

    if settings.api_token and token != settings.api_token:
        # In development mode, allow loopback calls from local desktop / extension
        if settings.environment == "development" and is_loopback_or_extension:
            return await call_next(request)

        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing X-Sahaay-Token header."},
        )

    return await call_next(request)


# Include v1 API Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(capabilities_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(actions_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(windows_router, prefix="/api/v1")
app.include_router(browser_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(storytelling_router, prefix="/api/v1")
app.include_router(research_router, prefix="/api/v1")

# Mount synthetic demonstration fixtures & visual artifacts
fixtures_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "fixtures"
if fixtures_path.exists():
    app.mount("/fixtures", StaticFiles(directory=str(fixtures_path)), name="fixtures")

if settings.artifacts_dir.exists():
    app.mount("/artifacts", StaticFiles(directory=str(settings.artifacts_dir)), name="artifacts")


@app.get("/")
async def root():
    return {
        "app": "Sahaay Core Backend",
        "version": "0.1.0",
        "status": "online",
        "docs_url": "/docs",
    }


def start() -> None:
    """Entry point for running uvicorn server."""
    import uvicorn

    uvicorn.run(
        "sahaay_core.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    start()
