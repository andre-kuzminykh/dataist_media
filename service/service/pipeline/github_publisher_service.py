"""
GitHubPublisherService — publishes HTML and assets to GitHub repository.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
"""

import base64
import logging
from datetime import datetime, timezone

import httpx

from service.core.config import config

logger = logging.getLogger(__name__)

_API = "https://api.github.com"


class GitHubPublisherService:
    """Publishes article HTML and cover image to a GitHub repository."""

    def __init__(self) -> None:
        self._token = config.GITHUB_TOKEN
        self._repo = config.GITHUB_REPO  # "owner/repo"

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def _put_file(
        self, path: str, content_bytes: bytes, message: str
    ) -> str:
        """Create or update a file in the repo. Returns the raw URL."""
        b64 = base64.b64encode(content_bytes).decode()

        # Check if file exists (to get sha for update)
        sha = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_API}/repos/{self._repo}/contents/{path}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                sha = resp.json().get("sha")

        payload = {
            "message": message,
            "content": b64,
            "branch": "main",
        }
        if sha:
            payload["sha"] = sha

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                f"{_API}/repos/{self._repo}/contents/{path}",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()

        raw_url = f"https://raw.githubusercontent.com/{self._repo}/refs/heads/main/{path}"
        logger.info("Published to GitHub: %s", raw_url)
        return raw_url

    async def publish(
        self,
        html_content: str,
        cover_image: bytes | None = None,
        folder_name: str | None = None,
    ) -> dict:
        """Publish article to GitHub repo in a date-based folder.

        Returns dict with HTTPS URLs:
        - html_url: raw URL to index.html
        - cover_url: raw URL to cover.png (or empty)
        """
        if not self._token or not self._repo:
            logger.warning("GitHub publishing skipped: no token or repo configured")
            return {"html_url": "", "cover_url": ""}

        if not folder_name:
            folder_name = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        result = {"html_url": "", "cover_url": ""}

        try:
            # Upload cover.png
            if cover_image:
                cover_url = await self._put_file(
                    f"{folder_name}/cover.png",
                    cover_image,
                    f"Add cover image for {folder_name}",
                )
                result["cover_url"] = cover_url

            # Upload index.html
            html_url = await self._put_file(
                f"{folder_name}/index.html",
                html_content.encode("utf-8"),
                f"Add article for {folder_name}",
            )
            result["html_url"] = html_url

        except Exception:
            logger.exception("GitHub publishing failed")

        return result
