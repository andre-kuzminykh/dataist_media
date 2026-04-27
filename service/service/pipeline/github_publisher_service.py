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
    ) -> None:
        """Create or update a file in the repo."""
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

    async def publish(
        self,
        html_content: str,
        cover_image: bytes | None = None,
        folder_name: str | None = None,
    ) -> dict:
        """Publish article to GitHub repo in a date-based folder.

        Returns dict with:
        - html_url: GitHub Pages URL (e.g. dataist.ai/2026-04-27/)
        - cover_url: GitHub Pages URL to cover.png
        - folder: the folder name used
        """
        logger.info("GitHub publish: token=%s, repo=%s", "set" if self._token else "MISSING", self._repo)
        if not self._token or not self._repo:
            logger.warning("GitHub publishing skipped: no token or repo configured")
            return {"html_url": "", "cover_url": "", "folder": ""}

        if not folder_name:
            folder_name = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        logger.info("GitHub publish: folder=%s", folder_name)

        result = {"html_url": "", "cover_url": "", "folder": folder_name}

        try:
            if cover_image:
                await self._put_file(
                    f"{folder_name}/cover.png",
                    cover_image,
                    f"Add cover image for {folder_name}",
                )
                result["cover_url"] = f"{self._pages_url}/{folder_name}/cover.png"

            await self._put_file(
                f"{folder_name}/index.html",
                html_content.encode("utf-8"),
                f"Add article for {folder_name}",
            )
            result["html_url"] = f"{self._pages_url}/{folder_name}/"

        except Exception:
            logger.exception("GitHub publishing failed")

        return result

    async def delete_folder(self, folder_name: str) -> bool:
        """Delete all files in a folder from the repo."""
        if not self._token or not self._repo:
            logger.warning("GitHub delete skipped: no token")
            return False

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{_API}/repos/{self._repo}/contents/{folder_name}",
                headers=self._headers(),
            )
            if resp.status_code != 200:
                logger.warning("GitHub folder not found: %s (status=%d)", folder_name, resp.status_code)
                return False
            files = resp.json()

        for f in files:
            path = f.get("path", "")
            sha = f.get("sha", "")
            if not path or not sha:
                continue
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.request(
                        "DELETE",
                        f"{_API}/repos/{self._repo}/contents/{path}",
                        headers=self._headers(),
                        json={
                            "message": f"Delete {path}",
                            "sha": sha,
                            "branch": "main",
                        },
                    )
                    logger.info("GitHub delete %s: status=%d", path, resp.status_code)
            except Exception:
                logger.exception("Failed to delete %s", path)

        return True
