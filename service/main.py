"""
Uvicorn entry point for the Dataist arXiv Pipeline API.

Run directly:
    python -m service.main

Feature IDs: F-CORE-ENTRYPOINT
"""

import logging

import uvicorn

from service.core.loader import app  # noqa: F401 (re-exported for uvicorn)
from service.core.config import config


def main() -> None:
    """Start the ASGI server with settings pulled from configuration."""
    # Configure root logger so service modules' logger.info() actually outputs
    logging.basicConfig(
        level=config.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    uvicorn.run(
        "service.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=True,
    )


if __name__ == "__main__":
    main()
