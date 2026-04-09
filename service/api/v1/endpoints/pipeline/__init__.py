"""
Pipeline API router.

## Traceability
Feature: F001, F002
"""

from fastapi import APIRouter

from service.api.v1.endpoints.pipeline.post import router as post_router

pipeline_router = APIRouter(prefix="/pipeline", tags=["pipeline"])
pipeline_router.include_router(post_router)
