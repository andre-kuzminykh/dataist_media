"""
Pipeline API router.

## Traceability
Feature: F001, F002
"""

from fastapi import APIRouter

from service.api.v1.endpoints.pipeline.post import router as post_router
from service.api.v1.endpoints.pipeline.steps import router as steps_router

pipeline_router = APIRouter(prefix="/pipeline", tags=["pipeline"])
pipeline_router.include_router(post_router)
pipeline_router.include_router(steps_router)
