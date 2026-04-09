"""
Test SC007 — ReviewCode routes to error answer on failure.

Given: Trigger data with valid URL but backend fails
When:  ReviewCode.run is called (PipelineAPI raises)
Then:  Returns ``answer_name="review_error"`` with error message

## Traceability
Feature: F002
Scenario: SC007
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from bot.node.review.code.review_code import ReviewCode


@pytest.mark.asyncio
async def test_review_code_error_on_http_failure(mock_state):
    """ReviewCode should route to 'review_error' when PipelineAPI raises."""
    trigger_data = {"url": "https://arxiv.org/abs/2301.12345"}

    # Build a realistic httpx.HTTPStatusError
    mock_request = MagicMock(spec=httpx.Request)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    http_error = httpx.HTTPStatusError(
        "Internal Server Error",
        request=mock_request,
        response=mock_response,
    )

    with patch.object(
        ReviewCode,
        "__init__",
        lambda self: setattr(self, "pipeline_api", AsyncMock()) or None,
    ):
        code = ReviewCode()
        code.pipeline_api.process_arxiv = AsyncMock(side_effect=http_error)

        result = await code.run(trigger_data, mock_state)

    assert result["answer_name"] == "review_error"
    assert "error" in result["data"]
    assert result["data"]["error"]  # non-empty string


@pytest.mark.asyncio
async def test_review_code_error_on_generic_exception(mock_state):
    """ReviewCode should route to 'review_error' on any unexpected exception."""
    trigger_data = {"url": "https://arxiv.org/abs/2301.12345"}

    with patch.object(
        ReviewCode,
        "__init__",
        lambda self: setattr(self, "pipeline_api", AsyncMock()) or None,
    ):
        code = ReviewCode()
        code.pipeline_api.process_arxiv = AsyncMock(
            side_effect=RuntimeError("connection reset"),
        )

        result = await code.run(trigger_data, mock_state)

    assert result["answer_name"] == "review_error"
    assert "connection reset" in result["data"]["error"]


@pytest.mark.asyncio
async def test_review_code_error_on_none_url(mock_state):
    """ReviewCode should return 'review_error' immediately when url is None."""
    trigger_data = {"url": None, "error": "invalid_url"}

    with patch.object(
        ReviewCode,
        "__init__",
        lambda self: setattr(self, "pipeline_api", AsyncMock()) or None,
    ):
        code = ReviewCode()

        result = await code.run(trigger_data, mock_state)

    assert result["answer_name"] == "review_error"
    assert result["data"]["error"] == "invalid_url"
    # PipelineAPI should NOT have been called
    code.pipeline_api.process_arxiv.assert_not_awaited()
