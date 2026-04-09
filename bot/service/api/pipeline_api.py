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
