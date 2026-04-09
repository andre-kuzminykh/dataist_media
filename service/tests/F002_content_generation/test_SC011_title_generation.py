"""
Test SC011 — Title generation and parsing.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenario: SC011 — Interactive title selection

## BDD
Given: Article parsed with short_intro and abstract
When:  ContentGeneratorService.generate_titles is called
Then:  Returns list of up to 10 title strings parsed from LLM output
"""

import re

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from service.service.pipeline.content_generator_service import ContentGeneratorService


@pytest.fixture
def mock_llm_titles_response():
    """Simulated LLM response with numbered titles."""
    return (
        "1. Новый подход к обучению языковых моделей\n"
        "2. Революция в архитектуре трансформеров\n"
        "3. Как масштабирование меняет правила игры в AI\n"
        "4. От теории к практике: прорыв в NLP\n"
        "5. Эффективное обучение без размеченных данных\n"
        "6. Будущее AI-агентов: новая парадигма\n"
        "7. Мультимодальный подход покоряет бенчмарки\n"
        "8. Когда меньше значит больше: дистилляция знаний\n"
        "9. Прорыв в рассуждениях: цепочки мыслей 2.0\n"
        "10. AI научился понимать контекст по-новому\n"
    )


class TestGenerateTitles:
    """Tests for ContentGeneratorService.generate_titles."""

    @pytest.mark.asyncio
    async def test_returns_list_of_strings(self, mock_llm_titles_response):
        """
        Given: LLM returns numbered list of titles
        When:  generate_titles is called
        Then:  Returns list of stripped title strings
        """
        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"titles_generation": "{short_intro}{abstract}"},
            "glossary": {},
        }
        service._call_llm = AsyncMock(return_value=mock_llm_titles_response)

        titles = await service.generate_titles("intro", "abstract", "test_profile")

        assert isinstance(titles, list)
        assert len(titles) == 10
        assert all(isinstance(t, str) for t in titles)

    @pytest.mark.asyncio
    async def test_strips_number_prefix(self, mock_llm_titles_response):
        """
        Given: LLM returns "1. Title\n2. Title"
        When:  Titles are parsed
        Then:  Number prefix is removed
        """
        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"titles_generation": "{short_intro}{abstract}"},
            "glossary": {},
        }
        service._call_llm = AsyncMock(return_value=mock_llm_titles_response)

        titles = await service.generate_titles("intro", "abstract", "test_profile")

        for title in titles:
            assert not re.match(r"^\d+[\.\)\-]", title), f"Title still has number prefix: {title}"

    @pytest.mark.asyncio
    async def test_limits_to_count(self):
        """
        Given: LLM returns more than requested count
        When:  generate_titles(count=5) is called
        Then:  Returns at most 5 titles
        """
        response = "\n".join(f"{i}. Title {i}" for i in range(1, 15))

        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"titles_generation": "{short_intro}{abstract}"},
            "glossary": {},
        }
        service._call_llm = AsyncMock(return_value=response)

        titles = await service.generate_titles("intro", "abstract", "test_profile", count=5)

        assert len(titles) <= 5

    @pytest.mark.asyncio
    async def test_handles_malformed_response(self):
        """
        Given: LLM returns non-numbered text
        When:  generate_titles is called
        Then:  Returns empty list (no numbered lines found)
        """
        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"titles_generation": "{short_intro}{abstract}"},
            "glossary": {},
        }
        service._call_llm = AsyncMock(return_value="Just some random text without numbers")

        titles = await service.generate_titles("intro", "abstract", "test_profile")

        assert isinstance(titles, list)
        assert len(titles) == 0


class TestRegenerateTitles:
    """Tests for ContentGeneratorService.regenerate_titles."""

    @pytest.mark.asyncio
    async def test_uses_custom_title_in_prompt(self):
        """
        Given: User provides a custom title
        When:  regenerate_titles is called
        Then:  Custom title appears in the prompt sent to LLM
        """
        captured_prompt = None

        async def capture_llm(prompt, max_tokens=1024):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "1. Title A\n2. Title B"

        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"titles_regeneration": "Based on: {custom_title} for {short_intro} about {abstract}"},
            "glossary": {},
        }
        service._call_llm = capture_llm

        await service.regenerate_titles("Мой заголовок", "intro", "abstract", "test_profile")

        assert "Мой заголовок" in captured_prompt


class TestEditCoverDescription:
    """Tests for ContentGeneratorService.edit_cover_description."""

    @pytest.mark.asyncio
    async def test_returns_updated_description(self):
        """
        Given: Current description and user feedback
        When:  edit_cover_description is called
        Then:  Returns updated string from LLM
        """
        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"cover_description_edit": "Current: {current_description} Edit: {user_feedback}"},
            "glossary": {},
        }
        service._call_llm = AsyncMock(return_value="Updated cover with more purple tones")

        result = await service.edit_cover_description(
            "Orange robot", "Add more purple", "test_profile"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_passes_feedback_to_prompt(self):
        """
        Given: User feedback text
        When:  edit_cover_description is called
        Then:  Feedback appears in prompt sent to LLM
        """
        captured_prompt = None

        async def capture_llm(prompt, max_tokens=1024):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "Updated description"

        service = ContentGeneratorService.__new__(ContentGeneratorService)
        service._client = MagicMock()
        service._model = "test"
        service._config_loader = MagicMock()
        service._config_loader.load_prompt_profile.return_value = {
            "prompts": {"cover_description_edit": "Current: {current_description} Edit: {user_feedback}"},
            "glossary": {},
        }
        service._call_llm = capture_llm

        await service.edit_cover_description(
            "Robot image", "Make it more abstract", "test_profile"
        )

        assert "Make it more abstract" in captured_prompt
        assert "Robot image" in captured_prompt
