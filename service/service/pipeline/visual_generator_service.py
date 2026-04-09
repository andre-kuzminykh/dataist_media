"""
VisualGeneratorService — generates cover images.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005, SC006

## Business Rules
BR009: Fallback cover on generation failure
BR012: Support reference image for cover generation
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from openai import AsyncOpenAI

from service.config.config_loader import ConfigLoader
from service.core.config import config

logger = logging.getLogger(__name__)


class VisualGeneratorService:
    """Generates cover images for editorial articles using OpenAI DALL-E."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self._loader = ConfigLoader()

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    async def generate_cover_prompt(
        self,
        article_summary: str,
        style_profile_id: str,
        prompt_profile_id: str,
    ) -> str:
        """Build an image-generation prompt from article meaning, style
        profile, and prompt template.

        Parameters
        ----------
        article_summary : str
            Short summary of the article used to seed the visual concept.
        style_profile_id : str
            Identifier of the visual-style profile (colours, mood, etc.).
        prompt_profile_id : str
            Identifier of the prompt profile containing the ``cover``
            template.

        Returns
        -------
        str
            A fully-rendered prompt string ready for the image model.
        """
        style = self._loader.load_style_profile(style_profile_id)
        palette = ", ".join(style.get("palette_names", []))
        mood = style.get("mood", "")

        prompt = self._loader.get_prompt(
            prompt_profile_id,
            "cover",
            article_summary=article_summary,
            palette=palette,
            mood=mood,
        )
        return prompt

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    async def generate_cover_image(self, prompt: str) -> bytes | None:
        """Call the OpenAI image-generation API and return raw image bytes.

        On any failure the method returns ``None`` so that the pipeline can
        apply the fallback-cover strategy (BR009).

        Parameters
        ----------
        prompt : str
            The fully-rendered image prompt.

        Returns
        -------
        bytes | None
            PNG image data, or ``None`` when generation fails.
        """
        try:
            response = await self._client.images.generate(
                model=config.OPENAI_IMAGE_MODEL,
                prompt=prompt,
                n=1,
                size="1792x1024",
                quality="hd",
                response_format="b64_json",
            )
            import base64

            b64_data = response.data[0].b64_json
            return base64.b64decode(b64_data)
        except Exception:
            logger.exception("Cover image generation failed — applying fallback (BR009)")
            return None

    # ------------------------------------------------------------------
    # Local persistence
    # ------------------------------------------------------------------

    async def save_cover_locally(self, image_data: bytes, slug: str) -> str:
        """Save cover image to the local asset directory.

        Parameters
        ----------
        image_data : bytes
            Raw PNG image bytes.
        slug : str
            URL-safe article slug used as sub-directory name.

        Returns
        -------
        str
            Relative path to the saved file (e.g. ``{slug}/cover.png``).
        """
        directory = Path(config.ASSET_STORAGE_PATH) / slug
        directory.mkdir(parents=True, exist_ok=True)

        file_path = directory / "cover.png"
        file_path.write_bytes(image_data)

        relative_path = f"{slug}/cover.png"
        logger.info("Cover saved locally: %s", relative_path)
        return relative_path

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def generate_and_save(
        self,
        article_summary: str,
        slug: str,
        style_profile_id: str,
        prompt_profile_id: str,
    ) -> dict:
        """Run the full cover-generation pipeline.

        1. Build the prompt.
        2. Generate the image.
        3. Save it locally.

        Parameters
        ----------
        article_summary : str
            Short summary for prompt construction.
        slug : str
            URL-safe slug for file storage.
        style_profile_id : str
            Visual-style profile identifier.
        prompt_profile_id : str
            Prompt profile identifier.

        Returns
        -------
        dict
            ``{"prompt": ..., "image_url": ..., "public_url": ...}``.
            On failure ``image_url`` and ``public_url`` are empty strings.
        """
        prompt = await self.generate_cover_prompt(
            article_summary, style_profile_id, prompt_profile_id
        )

        image_data = await self.generate_cover_image(prompt)

        if image_data is None:
            logger.warning("No cover image produced for slug=%s", slug)
            return {"prompt": prompt, "image_url": "", "public_url": ""}

        relative_path = await self.save_cover_locally(image_data, slug)
        public_url = f"{config.ASSET_PUBLIC_BASE_URL}/{relative_path}"

        return {
            "prompt": prompt,
            "image_url": relative_path,
            "public_url": public_url,
        }
