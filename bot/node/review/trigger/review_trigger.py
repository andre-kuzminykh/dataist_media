"""ReviewTrigger — extracts arXiv URL from message.

## Traceability
Feature: F001
Scenarios: SC001, SC002
"""

import re

from aiogram.types import Message
from aiogram.fsm.context import FSMContext

# Matches URLs like:
#   https://arxiv.org/abs/2301.00001
#   https://arxiv.org/abs/2301.00001v2
#   http://arxiv.org/pdf/2301.00001
#   https://arxiv.org/html/2301.00001v1
_ARXIV_RE = re.compile(
    r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}(?:v\d+)?)"
)


class ReviewTrigger:
    """Extract an arXiv URL from the incoming message text."""

    async def run(self, message: Message, state: FSMContext) -> dict:
        """Return ``{"url": "<matched_url>"}`` or an error dict."""
        text = message.text or ""
        match = _ARXIV_RE.search(text)
        if match:
            return {"url": match.group(0)}
        return {"url": None, "error": "invalid_url"}
