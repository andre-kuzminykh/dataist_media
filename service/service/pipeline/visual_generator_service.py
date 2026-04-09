"""
VisualGeneratorService — generates cover images using gpt-image-1.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005, SC006

## Business Rules
BR009: Fallback cover on generation failure
BR012: Support reference image for cover generation via images.edit
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from service.config.config_loader import ConfigLoader
from service.core.config import config

logger = logging.getLogger(__name__)

# Cache for downloaded reference image
_reference_cache: dict[str, bytes] = {}


class VisualGeneratorService:
    """Generates cover images using OpenAI gpt-image-1 with reference image."""

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
        """Build an image-generation prompt from article meaning + style."""
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
    # Reference image
    # ------------------------------------------------------------------

    async def _get_reference_image(self, style_profile_id: str) -> bytes | None:
        """Download and cache the reference image from the style profile."""
        style = self._loader.load_style_profile(style_profile_id)
        ref_url = style.get("reference_image_url", "")
        if not ref_url:
            return None

        if ref_url in _reference_cache:
            return _reference_cache[ref_url]

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(ref_url)
                resp.raise_for_status()
                _reference_cache[ref_url] = resp.content
                logger.info("Reference image downloaded: %d bytes", len(resp.content))
                return resp.content
        except Exception:
            logger.exception("Failed to download reference image: %s", ref_url)
            return None

    # ------------------------------------------------------------------
    # Image generation with reference (gpt-image-1 images.edit)
    # ------------------------------------------------------------------

    async def generate_cover_image(
        self,
        prompt: str,
        style_profile_id: str = "cinematic_orange_violet_v1",
    ) -> bytes | None:
        """Generate cover image using gpt-image-1 with reference image.

        Uses images.edit endpoint to pass the reference image as a source,
        so gpt-image-1 preserves the style (orange robot, violet tones).

        Falls back to images.generate (no reference) if reference unavailable.
        Returns None on any failure (BR009 fallback).
        """
        ref_image = await self._get_reference_image(style_profile_id)

        try:
            if ref_image:
                # Use images.edit with reference image
                logger.info("Generating cover with reference image (gpt-image-1 edit)")
                ref_file = io.BytesIO(ref_image)
                ref_file.name = "reference.png"

                response = await self._client.images.edit(
                    model="gpt-image-1",
                    image=[ref_file],
                    prompt=prompt,
                    n=1,
                    size="1536x1024",
                )

                b64_data = response.data[0].b64_json
                return base64.b64decode(b64_data)
            else:
                # Fallback: generate without reference
                logger.info("Generating cover without reference (dall-e-3 generate)")
                response = await self._client.images.generate(
                    model=config.OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    n=1,
                    size="1792x1024",
                    quality="hd",
                    response_format="b64_json",
                )

                b64_data = response.data[0].b64_json
                return base64.b64decode(b64_data)

        except Exception:
            logger.exception("Cover image generation failed — applying fallback (BR009)")
            return None

    # ------------------------------------------------------------------
    # Local persistence
    # ------------------------------------------------------------------

    async def save_cover_locally(self, image_data: bytes, slug: str) -> str:
        """Save cover image to the local asset directory."""
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
        """Run the full cover-generation pipeline."""
        prompt = await self.generate_cover_prompt(
            article_summary, style_profile_id, prompt_profile_id
        )

        image_data = await self.generate_cover_image(prompt, style_profile_id)

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
