"""ReviewProcessingAnswer — sends a "processing" status message.

## Traceability
Feature: F001
Scenarios: SC001
"""

from aiogram.types import Message

from bot.core import vocab


class ReviewProcessingAnswer:
    """Send a transient "processing" notification to the user."""

    async def run(
        self,
        event: Message,
        user_lang: str = "ru",
        data: dict | None = None,
    ) -> Message:
        """Send the processing message and return the sent ``Message``."""
        text = vocab.MSG_PROCESSING if user_lang == "ru" else vocab.MSG_PROCESSING_EN
        return await event.answer(text)
