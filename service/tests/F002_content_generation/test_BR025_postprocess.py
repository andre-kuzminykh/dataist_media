"""
Test BR025 — Editorial post-processing reduces English terms.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Business rule: BR025 — After generation, an editorial post-processing
pass replaces English terms with Russian equivalents via LLM.

## BDD
Given: A generated article body and the editorial_postprocess prompt
When:  postprocess_editorial is called
Then:  The LLM receives the body inside the postprocess prompt and its
       output replaces the article body; failures fall back to raw text
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from service.config.config_loader import ConfigLoader
from service.service.pipeline.content_generator_service import (
    ContentGeneratorService,
)

_PROFILE_ID = "default_ai_editorial_v1"


@pytest.fixture()
def generator() -> ContentGeneratorService:
    """ContentGeneratorService without a real OpenAI client.

    Built via __new__ (same pattern as SC011 tests) so that no API key
    is required; the real ConfigLoader reads the shipped profile.
    """
    service = ContentGeneratorService.__new__(ContentGeneratorService)
    service._client = MagicMock()
    service._model = "test"
    service._config_loader = ConfigLoader()
    return service


class TestPostprocessEditorial:
    """BR025: LLM-based cleanup of English terms."""

    @pytest.mark.asyncio
    async def test_returns_llm_output(self, generator):
        """
        Given: The postprocess prompt exists in the profile
        When:  postprocess_editorial is called
        Then:  The LLM response becomes the new article body
        """
        with patch.object(
            generator,
            "_call_llm",
            new=AsyncMock(return_value="Очищенный текст статьи."),
        ):
            result = await generator.postprocess_editorial(
                "Text with english terms.", _PROFILE_ID
            )

        assert result == "Очищенный текст статьи."

    @pytest.mark.asyncio
    async def test_prompt_contains_article_body(self, generator):
        """
        Given: An article body
        When:  postprocess_editorial is called
        Then:  The prompt sent to the LLM embeds that body
        """
        mock_llm = AsyncMock(return_value="ok")
        body = "Уникальный маркер текста ABC123."
        with patch.object(generator, "_call_llm", new=mock_llm):
            await generator.postprocess_editorial(body, _PROFILE_ID)

        sent_prompt = mock_llm.call_args.args[0]
        assert body in sent_prompt

    @pytest.mark.asyncio
    async def test_profile_prompt_mentions_key_replacements(self, generator):
        """
        Given: The shipped default profile
        When:  The editorial_postprocess prompt is loaded
        Then:  It instructs replacing key English terms per BR025
        """
        profile = generator._config_loader.load_prompt_profile(_PROFILE_ID)
        prompt = profile["prompts"]["editorial_postprocess"]

        assert "world model" in prompt
        assert "модель" in prompt
        assert "coding agent" in prompt
        assert "{article_body}" in prompt

    @pytest.mark.asyncio
    async def test_missing_prompt_returns_body_unchanged(self, generator):
        """
        Given: A profile without an editorial_postprocess prompt
        When:  postprocess_editorial is called
        Then:  The original body is returned and no LLM call is made
        """
        mock_llm = AsyncMock()
        with patch.object(
            generator._config_loader,
            "load_prompt_profile",
            return_value={"prompts": {}},
        ), patch.object(generator, "_call_llm", new=mock_llm):
            result = await generator.postprocess_editorial(
                "Original body.", _PROFILE_ID
            )

        assert result == "Original body."
        mock_llm.assert_not_awaited()


class TestGenerateEditorialFallback:
    """BR025 resilience: a failing postprocess must not lose the article."""

    @pytest.mark.asyncio
    async def test_raw_text_kept_when_postprocess_fails(self, generator):
        """
        Given: The postprocess step raises
        When:  generate_editorial runs
        Then:  The raw generated body is kept and no exception escapes
        """
        raw_body = "## Раздел\n\nСырой текст статьи."

        # Title, subtitle, and link extraction are patched below, so the
        # only remaining _call_llm call is the editorial body generation.
        with patch.object(
            generator, "_call_llm", new=AsyncMock(return_value=raw_body)
        ), patch.object(
            generator,
            "postprocess_editorial",
            new=AsyncMock(side_effect=RuntimeError("postprocess down")),
        ), patch.object(
            generator,
            "generate_title",
            new=AsyncMock(return_value="Заголовок"),
        ), patch.object(
            generator,
            "generate_subtitle",
            new=AsyncMock(return_value={"main": "Заголовок", "sub": ""}),
        ), patch.object(
            generator,
            "extract_links",
            new=AsyncMock(return_value={}),
        ):
            result = await generator.generate_editorial(
                {"abstract": "a", "article": "b", "figures": []},
                _PROFILE_ID,
            )

        assert result["article_body"] == raw_body
