"""ReviewSuccessAnswer — formats and sends the pipeline result.

## Traceability
Feature: F001, F002
Scenarios: SC001, SC005
"""

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from bot.core import vocab


class ReviewSuccessAnswer:
    """Format the pipeline result into a rich Telegram message."""

    async def run(
        self,
        event: Message,
        user_lang: str = "ru",
        data: dict | None = None,
    ) -> Message:
        """Build and send the success message with inline buttons."""
        data = data or {}
        pages = data.get("pages", {})

        title = data.get("messages", {}).get("ru_telegram_text", "Untitled")
        # Try to extract title from the telegram text or fallback
        if "<b>" in title and "</b>" in title:
            title = title.split("<b>")[1].split("</b>")[0]
        elif not title or title == "Untitled":
            title = "Article Review"

        ru_url = pages.get("ru_html_url", "")
        en_url = pages.get("en_html_url", "")

        links_parts: list[str] = []
        if ru_url:
            links_parts.append(f'\U0001f1f7\U0001f1fa <a href="{ru_url}">Русская версия</a>')
        if en_url:
            links_parts.append(f'\U0001f1ec\U0001f1e7 <a href="{en_url}">English version</a>')
        links_text = "\n".join(links_parts)

        if user_lang == "ru":
            text = vocab.MSG_SUCCESS.format(title=title, links=links_text)
        else:
            text = vocab.MSG_SUCCESS_EN.format(title=title, links=links_text)

        # Build inline keyboard
        buttons: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        if ru_url:
            row.append(InlineKeyboardButton(text=vocab.BTN_READ_RU, url=ru_url))
        if en_url:
            row.append(InlineKeyboardButton(text=vocab.BTN_READ_EN, url=en_url))
        if row:
            buttons.append(row)

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

        return await event.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
