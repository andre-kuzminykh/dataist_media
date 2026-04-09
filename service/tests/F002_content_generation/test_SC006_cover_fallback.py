"""
Test SC006 — Cover generation failure and fallback.

Feature: F002 — Editorial Content & HTML Generation
Scenario: SC006 — DALL-E image generation fails; pipeline applies fallback

Verifies that VisualGeneratorService.generate_cover_image returns None
when the OpenAI API raises an exception, and that generate_and_save
returns empty URLs when image generation fails (BR009 fallback).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from service.service.pipeline.visual_generator_service import VisualGeneratorService


# ---------------------------------------------------------------------------
# generate_cover_image — returns None on failure
# ---------------------------------------------------------------------------

class TestGenerateCoverImageFallback:
    """Tests that generate_cover_image returns None on OpenAI errors."""

    @pytest.mark.asyncio
    async def test_returns_none_on_api_exception(self) -> None:
        """
        Given an OpenAI client that raises an exception during image generation
        When generate_cover_image is called
        Then it returns None (BR009 fallback).
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._client.images.generate = AsyncMock(
                side_effect=Exception("API quota exceeded"),
            )
            service._loader = MagicMock()

            result = await service.generate_cover_image("test prompt")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout_error(self) -> None:
        """
        Given an OpenAI client that raises a timeout error
        When generate_cover_image is called
        Then it returns None.
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._client.images.generate = AsyncMock(
                side_effect=TimeoutError("Connection timed out"),
            )
            service._loader = MagicMock()

            result = await service.generate_cover_image("test prompt")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_value_error(self) -> None:
        """
        Given an OpenAI client that raises ValueError (bad response)
        When generate_cover_image is called
        Then it returns None.
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._client.images.generate = AsyncMock(
                side_effect=ValueError("Invalid response format"),
            )
            service._loader = MagicMock()

            result = await service.generate_cover_image("test prompt")

        assert result is None


# ---------------------------------------------------------------------------
# generate_and_save — empty URLs on failure
# ---------------------------------------------------------------------------

class TestGenerateAndSaveFallback:
    """Tests that generate_and_save returns empty URLs when generation fails."""

    @pytest.mark.asyncio
    async def test_returns_empty_urls_when_image_generation_fails(self) -> None:
        """
        Given generate_cover_image returns None (failure)
        When generate_and_save is called
        Then image_url and public_url are empty strings.
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._loader = MagicMock()

            # Mock generate_cover_prompt to return a prompt string
            service.generate_cover_prompt = AsyncMock(
                return_value="A beautiful illustration of AI",
            )
            # Mock generate_cover_image to return None (failure)
            service.generate_cover_image = AsyncMock(return_value=None)

            result = await service.generate_and_save(
                article_summary="Test summary",
                slug="test-slug",
                style_profile_id="test_style",
                prompt_profile_id="test_prompt",
            )

        assert result["image_url"] == ""
        assert result["public_url"] == ""
        assert result["prompt"] == "A beautiful illustration of AI"

    @pytest.mark.asyncio
    async def test_prompt_still_returned_on_failure(self) -> None:
        """
        Given generate_cover_image fails
        When generate_and_save is called
        Then the generated prompt is still included in the result.
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._loader = MagicMock()

            prompt_text = "Generate a cover showing neural networks"
            service.generate_cover_prompt = AsyncMock(return_value=prompt_text)
            service.generate_cover_image = AsyncMock(return_value=None)

            result = await service.generate_and_save(
                article_summary="Neural networks paper",
                slug="nn-paper",
                style_profile_id="style_v1",
                prompt_profile_id="prompt_v1",
            )

        assert result["prompt"] == prompt_text

    @pytest.mark.asyncio
    async def test_save_not_called_when_image_is_none(self) -> None:
        """
        Given generate_cover_image returns None
        When generate_and_save is called
        Then save_cover_locally is never invoked.
        """
        with patch("service.service.pipeline.visual_generator_service.config") as mock_config:
            mock_config.OPENAI_API_KEY = "fake-key"
            mock_config.OPENAI_IMAGE_MODEL = "dall-e-3"

            service = VisualGeneratorService.__new__(VisualGeneratorService)
            service._client = MagicMock()
            service._loader = MagicMock()

            service.generate_cover_prompt = AsyncMock(return_value="prompt")
            service.generate_cover_image = AsyncMock(return_value=None)
            service.save_cover_locally = AsyncMock()

            await service.generate_and_save(
                article_summary="Test",
                slug="test",
                style_profile_id="s",
                prompt_profile_id="p",
            )

        service.save_cover_locally.assert_not_called()
