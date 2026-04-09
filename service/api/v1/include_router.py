"""
Router inclusion for FastAPI app.

## Traceability
Feature: F001, F002
"""

from fastapi import FastAPI

from service.api.v1.endpoints.pipeline import pipeline_router

API_V1_PREFIX = "/api/v1"


def include_routers(app: FastAPI) -> None:
    """Include all API v1 routers into the FastAPI application."""
    app.include_router(pipeline_router, prefix=API_V1_PREFIX)
