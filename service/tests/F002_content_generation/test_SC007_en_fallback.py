"""
Test SC007 — RU page delivered even if EN translation fails.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenario: SC007 — RU delivered when EN fails
Business rule: BR010 — RU HTML delivered even when EN version fails

## BDD
Given: RU HTML is built successfully
When:  EN translation raises an error during the pipeline run
Then:  The result still contains the RU page URL, EN is skipped with a
       warning, and the pipeline does not raise
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from service.core.exceptions import GenerationError
from service.service.pipeline.pipeline_orchestrator_service import (
    PipelineOrchestratorService,
)


@pytest.fixture()
def orchestrator() -> PipelineOrchestratorService:
    """Orchestrator with every collaborator replaced by a mock.

    Built via __new__ (same pattern as SC011 tests) so that no OpenAI
    key is needed. HtmlBuilderService stays real (pure logic + Jinja
    template on disk), everything that would hit the network is mocked.
    """
    from service.service.pipeline.html_builder_service import HtmlBuilderService
    from service.service.pipeline.telegram_delivery_service import (
        TelegramDeliveryService,
    )

    orch = PipelineOrchestratorService.__new__(PipelineOrchestratorService)
    orch.html_builder = HtmlBuilderService()
    orch.telegram_delivery = TelegramDeliveryService()

    orch.url_resolver = MagicMock()
    orch.url_resolver.resolve.return_value = {
        "source_url": "https://arxiv.org/abs/2301.12345",
        "html_url": "https://arxiv.org/html/2301.12345v1",
        "valid": True,
    }

    orch.arxiv_parser = MagicMock()
    orch.arxiv_parser.parse = AsyncMock(
        return_value={
            "abstract": "Abstract text.",
            "article": "Full article text.",
            "figures": [],
            "source_url": "https://arxiv.org/abs/2301.12345",
            "html_url": "https://arxiv.org/html/2301.12345v1",
        }
    )

    orch.content_generator = MagicMock()
    orch.content_generator.generate_editorial = AsyncMock(
        return_value={
            "title": "Тестовый заголовок",
            "subtitle": "",
            "short_intro": "Краткое вступление.",
            "article_body": "## Раздел\n\nТекст статьи.",
            "links": {},
        }
    )
    orch.content_generator.generate_title = AsyncMock(
        return_value="Тестовый заголовок"
    )
    orch.content_generator.generate_subtitle = AsyncMock(
        return_value={"main": "Тестовый заголовок", "sub": "подзаголовок"}
    )
    orch.content_generator.extract_links = AsyncMock(
        return_value={
            "github_url": "",
            "huggingface_url": "",
            "project_url": "",
            "demo_url": "",
        }
    )
    orch.content_generator.generate_teaser = AsyncMock(
        return_value="Тизер статьи."
    )
    # SC007 precondition: EN translation fails
    orch.content_generator.translate_article = AsyncMock(
        side_effect=GenerationError(
            code="GEN_002",
            message="translation failed",
            stage="translation",
        )
    )

    orch.visual_generator = MagicMock()
    orch.visual_generator.generate_and_save = AsyncMock(
        return_value={"prompt": "p", "image_url": "", "public_url": ""}
    )

    orch.publisher = MagicMock()
    orch.publisher.publish_html = AsyncMock(
        return_value={
            "public_url": "http://localhost:8000/static/test/test_ru.html",
            "asset_urls": [],
            "published_at": "2026-01-01T00:00:00+00:00",
        }
    )

    return orch


class TestEnFailureFallback:
    """SC007: EN failure must not block RU delivery."""

    @pytest.mark.asyncio
    async def test_ru_url_present_when_en_fails(self, orchestrator):
        """
        Given: EN translation raises GenerationError
        When:  The full pipeline runs for ["ru", "en"]
        Then:  The RU page URL is present in the result
        """
        result = await orchestrator.run(
            source_url="https://arxiv.org/abs/2301.12345",
            target_languages=["ru", "en"],
        )

        assert result["pages"].get("ru_html_url")

    @pytest.mark.asyncio
    async def test_en_url_absent_and_warning_recorded(self, orchestrator):
        """
        Given: EN translation raises GenerationError
        When:  The full pipeline runs
        Then:  No EN page URL is produced and a warning explains why
        """
        result = await orchestrator.run(
            source_url="https://arxiv.org/abs/2301.12345",
            target_languages=["ru", "en"],
        )

        assert "en_html_url" not in result["pages"]
        warnings = result["diagnostics"]["warnings"]
        assert any("EN HTML" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_status_is_completed_with_warnings(self, orchestrator):
        """
        Given: EN translation raises GenerationError
        When:  The full pipeline runs
        Then:  Status degrades to completed_with_warnings, not a failure
        """
        result = await orchestrator.run(
            source_url="https://arxiv.org/abs/2301.12345",
            target_languages=["ru", "en"],
        )

        assert result["status"] == "completed_with_warnings"

    @pytest.mark.asyncio
    async def test_en_failure_step_recorded(self, orchestrator):
        """
        Given: EN translation raises GenerationError
        When:  The full pipeline runs
        Then:  The failed EN build step is present in diagnostics.steps
        """
        result = await orchestrator.run(
            source_url="https://arxiv.org/abs/2301.12345",
            target_languages=["ru", "en"],
        )

        step_names = {
            s["name"]: s["status"] for s in result["diagnostics"]["steps"]
        }
        assert step_names.get("build_publish_html_en") == "failed"
        assert step_names.get("publish_html_ru") == "ok"

    @pytest.mark.asyncio
    async def test_ru_only_run_unaffected(self, orchestrator):
        """
        Given: The same failing EN translator
        When:  The pipeline runs for ["ru"] only
        Then:  The run succeeds without touching translation at all
        """
        result = await orchestrator.run(
            source_url="https://arxiv.org/abs/2301.12345",
            target_languages=["ru"],
        )

        assert result["pages"].get("ru_html_url")
        orchestrator.content_generator.translate_article.assert_not_awaited()
