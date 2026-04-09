"""
Uvicorn entry point for the Dataist arXiv Pipeline API.

Run directly:
    python -m service.main

Feature IDs: F-CORE-ENTRYPOINT
"""

import uvicorn

from service.core.loader import app  # noqa: F401 (re-exported for uvicorn)
from service.core.config import config


def main() -> None:
    """Start the ASGI server with settings pulled from configuration."""
    uvicorn.run(
        "service.main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=True,
    )


if __name__ == "__main__":
    main()
