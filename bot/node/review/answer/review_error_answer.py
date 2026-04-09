"""ReviewErrorAnswer — sends an error message to the user.

## Traceability
Feature: F001
Scenarios: SC002
"""

from aiogram.types import Message

from bot.core import vocab


class ReviewErrorAnswer:
    """Send a human-readable error message."""

    async def run(
        self,
        event: Message,
        user_lang: str = "ru",
        data: dict | None = None,
    ) -> Message:
        """Format and send the error message."""
        data = data or {}
        error = data.get("error", "unknown_error")

        if error == "invalid_url":
            text = vocab.MSG_INVALID_URL if user_lang == "ru" else vocab.MSG_INVALID_URL_EN
        else:
            if user_lang == "ru":
                text = vocab.MSG_ERROR.format(error=error)
            else:
                text = vocab.MSG_ERROR_EN.format(error=error)

        return await event.answer(text)
