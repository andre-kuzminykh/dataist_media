"""
PublisherService — publishes HTML pages to static hosting.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005, SC008

## Business Rules
NFR-8: Idempotent HTML publishing
NFR-9: Trace/log for each run
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from service.core.config import config

logger = logging.getLogger(__name__)


class PublisherService:
    """Publishes HTML pages and binary assets to the configured static-hosting
    directory.

    Publishing is idempotent (NFR-8): re-publishing the same slug and
    filename silently overwrites the previous version.  Every operation
    is logged for traceability (NFR-9).
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish_html(
        self,
        html: str,
        slug: str,
        filename: str,
        assets: list[str] | None = None,
    ) -> dict:
        """Save an HTML file to the asset storage directory.

        Creates the target directory if it does not exist and writes the
        HTML content.  The operation is idempotent — an existing file at
        the same path is silently overwritten.

        Parameters
        ----------
        html : str
            Rendered HTML content.
        slug : str
            URL-safe article identifier (used as sub-directory).
        filename : str
            Target filename (e.g. ``"my-article_ru.html"``).
        assets : list[str] | None
            Optional list of already-published asset relative paths to
            include in the response.

        Returns
        -------
        dict
            ``{"public_url": ..., "asset_urls": [...], "published_at": ...}``
        """
        target_dir = Path(config.ASSET_STORAGE_PATH) / slug
        self._ensure_directory(str(target_dir))

        file_path = target_dir / filename
        file_path.write_text(html, encoding="utf-8")

        public_url = f"{config.ASSET_PUBLIC_BASE_URL}/{slug}/{filename}"
        iso_now = datetime.now(timezone.utc).isoformat()

        asset_urls = []
        if assets:
            asset_urls = [
                f"{config.ASSET_PUBLIC_BASE_URL}/{a}" for a in assets
            ]

        logger.info(
            "Published HTML: url=%s slug=%s at=%s",
            public_url,
            slug,
            iso_now,
        )

        return {
            "public_url": public_url,
            "asset_urls": asset_urls,
            "published_at": iso_now,
        }

    async def publish_asset(
        self,
        data: bytes,
        slug: str,
        filename: str,
    ) -> str:
        """Save a binary asset (image, font, etc.) and return its public URL.

        Parameters
        ----------
        data : bytes
            Raw binary content.
        slug : str
            URL-safe article identifier (sub-directory).
        filename : str
            Target filename (e.g. ``"cover.png"``).

        Returns
        -------
        str
            The public URL of the saved asset.
        """
        target_dir = Path(config.ASSET_STORAGE_PATH) / slug
        self._ensure_directory(str(target_dir))

        file_path = target_dir / filename
        file_path.write_bytes(data)

        public_url = f"{config.ASSET_PUBLIC_BASE_URL}/{slug}/{filename}"
        logger.info("Published asset: url=%s", public_url)
        return public_url

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_directory(self, path: str) -> None:
        """Create the directory (and parents) if it does not already exist.

        Parameters
        ----------
        path : str
            Absolute or relative directory path.
        """
        Path(path).mkdir(parents=True, exist_ok=True)
