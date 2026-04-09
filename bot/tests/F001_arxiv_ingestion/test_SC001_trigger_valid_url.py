"""
Test SC001 — ReviewTrigger extracts valid arXiv URLs.

Given: Message with valid arXiv URL
When:  ReviewTrigger.run is called
Then:  Returns dict with ``url`` key containing the matched URL

## Traceability
Feature: F001
Scenario: SC001
"""

import pytest

from bot.node.review.trigger.review_trigger import ReviewTrigger


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, expected_url",
    [
        pytest.param(
            "https://arxiv.org/abs/2301.12345",
            "https://arxiv.org/abs/2301.12345",
            id="plain_abs_url",
        ),
        pytest.param(
            "Check this paper https://arxiv.org/abs/2301.12345v2 it's good",
            "https://arxiv.org/abs/2301.12345v2",
            id="abs_url_with_version_in_sentence",
        ),
        pytest.param(
            "/review https://arxiv.org/abs/2301.12345",
            "https://arxiv.org/abs/2301.12345",
            id="command_prefix_abs_url",
        ),
        pytest.param(
            "https://arxiv.org/html/2301.12345v1",
            "https://arxiv.org/html/2301.12345v1",
            id="html_url_with_version",
        ),
    ],
)
async def test_trigger_extracts_valid_url(
    text: str,
    expected_url: str,
    mock_message,
    mock_state,
):
    """ReviewTrigger should return the arXiv URL for each valid input."""
    mock_message.text = text

    trigger = ReviewTrigger()
    result = await trigger.run(mock_message, mock_state)

    assert result["url"] == expected_url
    assert "error" not in result
