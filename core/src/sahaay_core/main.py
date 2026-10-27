"""Sahaay Core Backend Main Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sahaay_core.api.v1.actions import router as actions_router
from sahaay_core.api.v1.audit import router as audit_router
from sahaay_core.api.v1.browser import router as browser_router
from sahaay_core.api.v1.capabilities import router as capabilities_router
from sahaay_core.api.v1.health import router as health_router
from sahaay_core.api.v1.sessions import router as sessions_router
from sahaay_core.api.v1.sources import router as sources_router
from sahaay_core.api.v1.tasks import router as tasks_router
from sahaay_core.api.v1.windows import router as windows_router
from sahaay_core.config.logging import logger
from sahaay_core.config.settings import settings
from sahaay_core.storage.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle hooks: initialize database and verify configuration."""
    logger.info("Initializing Sahaay Core Backend (Stage 01 Foundation)...")
    logger.info(f"Local-only mode: {settings.local_only_mode}")
    logger.info(f"Listening address: {settings.host}:{settings.port}")
    await init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Sahaay Core Backend.")


app = FastAPI(
    title="Sahaay Core Backend",
    version="0.1.0",
    description="Authoritative backend orchestrator for Sahaay Desktop AI Agent",
    lifespan=lifespan,
)

# CORS: strictly allow loopback desktop & extension origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:5173",
        "http://localhost:3000",
        "chrome-extension://*",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_token_middleware(request: Request, call_next):
    """Enforce token authentication on internal API routes.

    Health endpoint is public for startup probing; all others require valid X-Sahaay-Token.
    """
    path = request.url.path
    if path in ("/api/v1/health", "/docs", "/openapi.json"):
        return await call_next(request)

    token = request.headers.get("X-Sahaay-Token")
    if settings.api_token and token != settings.api_token:
        # In development/test mode without a token header, allow loopback localhost calls if configured
        client_host = request.client.host if request.client else ""
        if settings.environment == "development" and client_host in (
            "127.0.0.1",
            "localhost",
            "testclient",
        ):
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
