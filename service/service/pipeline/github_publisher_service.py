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
        # Read config lazily on each access via properties below
        pass

    @property
    def _token(self) -> str:
        return config.GITHUB_TOKEN

    @property
    def _repo(self) -> str:
        return config.GITHUB_REPO

    @property
    def _pages_url(self) -> str:
        return config.GITHUB_PAGES_URL.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def _put_file(
        self, path: str, content_bytes: bytes, message: str
    ) -> str:
        """Create or update a file in the repo. Returns the pages URL."""
        logger.info("GitHub _put_file: repo=%s path=%s size=%d", self._repo, path, len(content_bytes))
        b64 = base64.b64encode(content_bytes).decode()

        sha = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_API}/repos/{self._repo}/contents/{path}",
                headers=self._headers(),
            )
            logger.info("GitHub check existing: status=%d", resp.status_code)
            if resp.status_code == 200:
                sha = resp.json().get("sha")
            elif resp.status_code == 401:
                logger.error("GitHub token INVALID — 401 Unauthorized")
                raise RuntimeError("GitHub token invalid (401)")

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
            logger.info("GitHub put: status=%d", resp.status_code)
            if resp.status_code >= 400:
                logger.error("GitHub put failed: %s", resp.text[:500])
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
        logger.info("GitHub publish: token=%s, repo=%s", "set" if self._token else "MISSING", self._repo)
        if not self._token or not self._repo:
            logger.warning("GitHub publishing skipped: no token or repo configured")
            return {"html_url": "", "cover_url": ""}

        if not folder_name:
            folder_name = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info("GitHub publish: folder=%s", folder_name)

        result = {"html_url": "", "cover_url": ""}

        try:
            # Upload cover.png
            if cover_image:
                await self._put_file(
                    f"{folder_name}/cover.png",
                    cover_image,
                    f"Add cover image for {folder_name}",
                )
                # Use GitHub Pages URL (dataist.ai/folder/cover.png)
                result["cover_url"] = f"{self._pages_url}/{folder_name}/cover.png"

            # Upload index.html
            await self._put_file(
                f"{folder_name}/index.html",
                html_content.encode("utf-8"),
                f"Add article for {folder_name}",
            )
            # Pages URL: dataist.ai/folder/ (browser auto-loads index.html)
            result["html_url"] = f"{self._pages_url}/{folder_name}/"

        except Exception:
            logger.exception("GitHub publishing failed")

        return result
