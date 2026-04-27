"""
FastAPI application factory and middleware configuration.
"""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from service.core.config import config

# Configure root logger immediately on import (works with both uvicorn reload modes)
logging.basicConfig(
    level=config.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)

app = FastAPI(
    title="Dataist arXiv Pipeline API",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS -- allow all origins during development; tighten for production.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static file serving for published assets (images, HTML articles, etc.)
# ---------------------------------------------------------------------------
_static_dir = config.ASSET_STORAGE_PATH
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir, html=True), name="static")


# ---------------------------------------------------------------------------
# Startup event: include routers & exception handlers (avoids circular imports)
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _setup_routes() -> None:
    from service.api.v1.include_router import include_routers
    from service.api.v1.exception_handlers import register_exception_handlers

    include_routers(app)
    register_exception_handlers(app)
