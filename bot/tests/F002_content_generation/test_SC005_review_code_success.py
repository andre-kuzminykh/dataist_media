"""
Test SC005 — ReviewCode routes to success answer on valid pipeline result.

Given: Trigger data with valid URL
When:  ReviewCode.run is called (PipelineAPI mocked)
Then:  Returns ``answer_name="review_success"`` with pipeline data

## Traceability
Feature: F002
Scenario: SC005
"""

import pytest
from unittest.mock import AsyncMock, patch

from bot.node.review.code.review_code import ReviewCode


@pytest.mark.asyncio
async def test_review_code_success(mock_state, sample_pipeline_result):
    """ReviewCode should route to 'review_success' when the pipeline succeeds."""
    trigger_data = {"url": "https://arxiv.org/abs/2301.12345"}

    with patch.object(
        ReviewCode,
        "__init__",
        lambda self: setattr(self, "pipeline_api", AsyncMock()) or None,
    ):
        code = ReviewCode()
        code.pipeline_api.process_arxiv = AsyncMock(return_value=sample_pipeline_result)

        result = await code.run(trigger_data, mock_state)

    assert result["answer_name"] == "review_success"
    assert result["data"] is sample_pipeline_result
    assert "pages" in result["data"]
    assert "ru_html_url" in result["data"]["pages"]
    assert "en_html_url" in result["data"]["pages"]


@pytest.mark.asyncio
async def test_review_code_success_calls_api_with_url(mock_state, sample_pipeline_result):
    """ReviewCode should forward the arXiv URL to PipelineAPI.process_arxiv."""
    url = "https://arxiv.org/abs/2301.12345"
    trigger_data = {"url": url}

    with patch.object(
        ReviewCode,
        "__init__",
        lambda self: setattr(self, "pipeline_api", AsyncMock()) or None,
    ):
        code = ReviewCode()
        code.pipeline_api.process_arxiv = AsyncMock(return_value=sample_pipeline_result)

        await code.run(trigger_data, mock_state)

    code.pipeline_api.process_arxiv.assert_awaited_once_with(url)
