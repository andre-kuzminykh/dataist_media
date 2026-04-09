"""
Test SC002 — ReviewTrigger handles invalid URLs.

Given: Message without valid arXiv URL
When:  ReviewTrigger.run is called
Then:  Returns dict with ``url=None`` and ``error="invalid_url"``

## Traceability
Feature: F001
Scenario: SC002
"""

import pytest

from bot.node.review.trigger.review_trigger import ReviewTrigger


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("hello world", id="plain_text"),
        pytest.param("https://google.com", id="non_arxiv_url"),
        pytest.param("arxiv.org/abs/2301.12345", id="missing_protocol"),
        pytest.param("", id="empty_string"),
    ],
)
async def test_trigger_rejects_invalid_url(
    text: str,
    mock_message,
    mock_state,
):
    """ReviewTrigger should return url=None and error='invalid_url'."""
    mock_message.text = text

    trigger = ReviewTrigger()
    result = await trigger.run(mock_message, mock_state)

    assert result["url"] is None
    assert result["error"] == "invalid_url"
