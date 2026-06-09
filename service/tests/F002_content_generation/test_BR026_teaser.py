"""
Test BR026 — Telegram teaser is an engaging 3-paragraph summary.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenario: SC013 — Final message with teaser
Business rule: BR026 — Teaser = engaging summary, simple Russian, no jargon

## BDD
Given: An article title and short intro
When:  generate_teaser is called with the teaser prompt
Then:  The prompt instructs a 3-paragraph plain-language summary
       and the result is returned as-is from the LLM
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from service.config.config_loader import ConfigLoader
from service.service.pipeline.content_generator_service import ContentGeneratorService


class TestTeaserPrompt:
    """BR026: teaser prompt must demand plain-language, no English jargon."""

    def test_prompt_forbids_english_terms(self):
        """
        Given: The default teaser prompt
        When:  Loaded from config
        Then:  It explicitly forbids English jargon terms
        """
        loader = ConfigLoader()
        profile = loader.load_prompt_profile("default_ai_editorial_v1")
        teaser = profile["prompts"]["teaser"]

        # Must mention banning English terms / jargon
        assert "ЗАПРЕЩЕНЫ" in teaser or "запрещ" in teaser.lower()
        # Sample forbidden terms must be listed
        assert "compression" in teaser
        assert "memory pipeline" in teaser or "pipeline" in teaser

    def test_prompt_requires_three_paragraphs(self):
        """
        Given: The teaser prompt
        When:  Inspected
        Then:  It requires a 3-paragraph structure (hook → essence → CTA)
        """
        loader = ConfigLoader()
        profile = loader.load_prompt_profile("default_ai_editorial_v1")
        teaser = profile["prompts"]["teaser"]

        assert "3 абзац" in teaser
        assert "В обзоре разберём" in teaser or "разбираем" in teaser

    def test_prompt_has_language_and_placeholders(self):
        """
        Given: The teaser prompt
        When:  Checked for placeholders
        Then:  It contains {language}, {title}, {short_intro}
        """
        loader = ConfigLoader()
        profile = loader.load_prompt_profile("default_ai_editorial_v1")
        teaser = profile["prompts"]["teaser"]

        assert "{language}" in teaser
        assert "{title}" in teaser
        assert "{short_intro}" in teaser


class TestGenerateTeaser:
    """BR026: generate_teaser returns LLM output for the teaser prompt."""

    @pytest.mark.asyncio
    async def test_returns_llm_teaser_text(self):
        """
        Given: A stubbed LLM returning a 3-paragraph teaser
        When:  generate_teaser is called
        Then:  The teaser text is returned unchanged
        """
        svc = ContentGeneratorService.__new__(ContentGeneratorService)
        svc._client = MagicMock()
        svc._model = "test"
        svc._config_loader = ConfigLoader()

        fake_teaser = (
            "Математика долго считалась территорией человека.\n\n"
            "Теперь ИИ участвует в исследовании целиком.\n\n"
            "В этом обзоре разбираем, как устроен такой союз."
        )
        svc._call_llm = AsyncMock(return_value=fake_teaser)

        result = await svc.generate_teaser(
            title="Как ИИ-соавтор решает задачи",
            short_intro="ИИ помогает математикам",
            language="ru",
            prompt_profile_id="default_ai_editorial_v1",
        )

        assert result == fake_teaser
        assert result.count("\n\n") == 2  # exactly 3 paragraphs

    @pytest.mark.asyncio
    async def test_teaser_prompt_formatted_with_inputs(self):
        """
        Given: A title and intro
        When:  generate_teaser is called
        Then:  The prompt sent to the LLM contains both values
        """
        svc = ContentGeneratorService.__new__(ContentGeneratorService)
        svc._client = MagicMock()
        svc._model = "test"
        svc._config_loader = ConfigLoader()

        captured = {}

        async def capture(prompt, max_tokens=512):
            captured["prompt"] = prompt
            return "ok"

        svc._call_llm = capture

        await svc.generate_teaser(
            title="Уникальный Заголовок 123",
            short_intro="Особое содержание 456",
            language="ru",
            prompt_profile_id="default_ai_editorial_v1",
        )

        assert "Уникальный Заголовок 123" in captured["prompt"]
        assert "Особое содержание 456" in captured["prompt"]
