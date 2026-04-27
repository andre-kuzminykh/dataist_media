"""HTTP client to backend pipeline API.

## Traceability
Feature: F001, F002
Scenarios: SC001, SC005
"""

import httpx

from bot.core.config import config


class PipelineAPI:
    """Async HTTP client for the article-review pipeline."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or config.BACKEND_URL).rstrip("/")

    async def process_arxiv(
        self,
        source_url: str,
        prompt_profile_id: str = "default_ai_editorial_v1",
        style_profile_id: str = "cinematic_orange_violet_v1",
        reference_image_url: str = "",
    ) -> dict:
        """POST an arXiv URL to the backend pipeline and return the result.

        Raises ``httpx.HTTPStatusError`` on non-2xx responses.
        """
        payload = {
            "source_url": source_url,
            "prompt_profile_id": prompt_profile_id,
            "style_profile_id": style_profile_id,
            "reference_image_url": reference_image_url,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/pipeline/process",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def parse_article(self, source_url: str) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/parse", json={"source_url": source_url})
            resp.raise_for_status()
            return resp.json()

    async def generate_titles(self, short_intro: str, abstract: str) -> list[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/generate-titles", json={"short_intro": short_intro, "abstract": abstract})
            resp.raise_for_status()
            return resp.json()["titles"]

    async def regenerate_titles(self, custom_title: str, short_intro: str, abstract: str) -> list[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/regenerate-titles", json={"custom_title": custom_title, "short_intro": short_intro, "abstract": abstract})
            resp.raise_for_status()
            return resp.json()["titles"]

    async def generate_editorial(self, parsed_article: dict, chosen_title: str) -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/generate-editorial", json={"parsed_article": parsed_article, "chosen_title": chosen_title})
            resp.raise_for_status()
            return resp.json()

    async def generate_cover_description(self, article_summary: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/generate-cover-description", json={"article_summary": article_summary})
            resp.raise_for_status()
            return resp.json()["description"]

    async def edit_cover_description(self, current_description: str, user_feedback: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/edit-cover-description", json={"current_description": current_description, "user_feedback": user_feedback})
            resp.raise_for_status()
            return resp.json()["description"]

    async def generate_cover(self, description: str, slug: str, previous_cover_url: str = "") -> dict:
        payload = {"description": description, "slug": slug}
        if previous_cover_url:
            payload["previous_cover_url"] = previous_cover_url
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/generate-cover", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def build_and_publish(self, title: str, subtitle: str, article_body: str, short_intro: str, cover_image_url: str, links: dict, figures: list, source_url: str) -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/v1/pipeline/build-and-publish", json={
                "title": title, "subtitle": subtitle, "article_body": article_body,
                "short_intro": short_intro, "cover_image_url": cover_image_url,
                "links": links, "figures": figures, "source_url": source_url
            })
            resp.raise_for_status()
            return resp.json()

    async def delete_article(self, folder: str) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/pipeline/delete-article",
                json={"folder": folder},
            )
            resp.raise_for_status()
            return resp.json().get("ok", False)

    async def download_cover_image(self, cover_url: str) -> bytes | None:
        """Download cover image bytes from the service's internal static URL."""
        import re
        import logging
        logger = logging.getLogger(__name__)

        internal_url = re.sub(r"https?://[^/]+", self.base_url, cover_url, count=1)
        logger.info("Downloading cover: %s → %s", cover_url, internal_url)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(internal_url)
                resp.raise_for_status()
                logger.info("Cover downloaded: %d bytes", len(resp.content))
                return resp.content
        except Exception as exc:
            logger.exception("Cover download failed: %s", exc)
            return None
