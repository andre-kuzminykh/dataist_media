"""
Exception handlers for the API.

## Traceability
Feature: F001, F002
NFR-4: Errors must be explainable
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from service.core.exceptions import AppException


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "stage": exc.stage,
                    "retriable": exc.retriable,
                },
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(exc),
                    "stage": "unknown",
                    "retriable": True,
                },
            },
        )
