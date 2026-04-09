"""
TelegramDeliveryService — sends messages via Telegram Bot API.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005

## Business Rules
BR008: Deliver Telegram messages with links
"""

from __future__ import annotations

import logging

import httpx

from service.core.config import config
from service.core.exceptions import DeliveryError

logger = logging.getLogger(__name__)


class TelegramDeliveryService:
    """Sends formatted messages to Telegram chats via the Bot API."""

    _API_BASE = "https://api.telegram.org"

    def __init__(self) -> None:
        self._token = config.TELEGRAM_BOT_TOKEN

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
    ) -> dict:
        """Send a text message to a Telegram chat.

        Parameters
        ----------
        chat_id : str
            Target chat / channel identifier.
        text : str
            Message body (may contain HTML formatting when
            ``parse_mode="HTML"``).
        parse_mode : str
            Telegram parse mode — ``"HTML"`` (default) or
            ``"MarkdownV2"``.

        Returns
        -------
        dict
            ``{"ok": True, "message_id": <int>}`` on success.

        Raises
        ------
        DeliveryError
            When the Telegram API returns a non-OK response or a network
            error occurs.
        """
        url = f"{self._API_BASE}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Telegram HTTP error: %s", exc)
            raise DeliveryError(
                code="TG_HTTP_001",
                message=f"Telegram API request failed: {exc}",
                stage="telegram_delivery",
                retriable=True,
            ) from exc

        if not data.get("ok"):
            description = data.get("description", "Unknown Telegram error")
            error_code = data.get("error_code", 0)
            logger.error(
                "Telegram API error: code=%s description=%s",
                error_code,
                description,
            )
            raise DeliveryError(
                code=f"TG_API_{error_code}",
                message=f"Telegram API error: {description}",
                stage="telegram_delivery",
                retriable=error_code >= 500,
            )

        message_id = data.get("result", {}).get("message_id")
        logger.info(
            "Telegram message sent: chat_id=%s message_id=%s",
            chat_id,
            message_id,
        )
        return {"ok": True, "message_id": message_id}

    # ------------------------------------------------------------------
    # Message formatting
    # ------------------------------------------------------------------

    def _format_telegram_message(
        self,
        title: str,
        ru_url: str,
        en_url: str,
        teaser_ru: str,
        teaser_en: str,
        cover_url: str,
    ) -> tuple[str, str]:
        """Create Telegram message texts for RU and EN audiences.

        Both messages use Telegram-compatible HTML formatting and include
        links to the article pages.

        Parameters
        ----------
        title : str
            Article headline.
        ru_url : str
            URL to the Russian HTML page.
        en_url : str
            URL to the English HTML page.
        teaser_ru : str
            Short Russian teaser text.
        teaser_en : str
            Short English teaser text.
        cover_url : str
            Public URL to the cover image.

        Returns
        -------
        tuple[str, str]
            ``(ru_text, en_text)`` — formatted message strings.
        """
        ru_text = (
            f"<b>{title}</b>\n\n"
            f"{teaser_ru}\n\n"
            f'<a href="{ru_url}">Читать статью</a>'
        )
        if en_url:
            ru_text += f' | <a href="{en_url}">Read in English</a>'
        if cover_url:
            ru_text += f'\n\n<a href="{cover_url}">&#8205;</a>'

        en_text = (
            f"<b>{title}</b>\n\n"
            f"{teaser_en}\n\n"
            f'<a href="{en_url}">Read the article</a>'
        )
        if ru_url:
            en_text += f' | <a href="{ru_url}">Читать на русском</a>'
        if cover_url:
            en_text += f'\n\n<a href="{cover_url}">&#8205;</a>'

        return ru_text, en_text
