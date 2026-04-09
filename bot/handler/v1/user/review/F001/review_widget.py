"""
Widget: Interactive arXiv Review Pipeline.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001, SC002, SC005, SC011, SC012

Flow:
1. Send arXiv URL (with or without /review) → parse → 10 titles
2. Pick title (button) OR type text → use as title directly
3. Show cover description → type edits (LLM refines) or own prompt → generate
4. Teaser + "Полный обзор" hyperlink + [RU/EN] toggle button
5. All intermediate messages are deleted, only final stays
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from bot.core import vocab
from bot.state.review_state import ReviewStates
from bot.callback.review_callback import TitleCallback, CoverCallback
from bot.service.api.pipeline_api import PipelineAPI
from bot.node.review.trigger.review_trigger import ReviewTrigger

logger = logging.getLogger(__name__)

router = Router(name="review_widget")
_trigger = ReviewTrigger()
_api = PipelineAPI()


# ── Helpers ───────────────────────────────────────────────────────────

def _lang(event) -> str:
    user = getattr(event, "from_user", None)
    if user:
        lc = user.language_code or "ru"
        return "ru" if lc.startswith("ru") else "en"
    return "ru"


async def _delete_safe(msg: Message) -> None:
    """Delete a message, ignoring errors."""
    try:
        await msg.delete()
    except Exception:
        pass


async def _send_and_track(
    target: Message, text: str, state: FSMContext, **kwargs
) -> Message:
    """Send message, save its id for later deletion."""
    sent = await target.answer(text, **kwargs)
    data = await state.get_data()
    tracked: list[int] = data.get("_tracked_msgs", [])
    tracked.append(sent.message_id)
    await state.update_data(_tracked_msgs=tracked)
    return sent


async def _cleanup_tracked(chat_id: int, state: FSMContext, bot) -> None:
    """Delete all tracked intermediate messages."""
    data = await state.get_data()
    for mid in data.get("_tracked_msgs", []):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(_tracked_msgs=[])


def _titles_keyboard(titles: list[str]) -> InlineKeyboardMarkup:
    row1 = [
        InlineKeyboardButton(
            text=str(i + 1),
            callback_data=TitleCallback(action="pick", index=i + 1).pack(),
        )
        for i in range(min(5, len(titles)))
    ]
    row2 = [
        InlineKeyboardButton(
            text=str(i + 1),
            callback_data=TitleCallback(action="pick", index=i + 1).pack(),
        )
        for i in range(5, min(10, len(titles)))
    ]
    rows = []
    if row1:
        rows.append(row1)
    if row2:
        rows.append(row2)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cover_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=vocab.BTN_GENERATE_COVER,
                    callback_data=CoverCallback(action="generate").pack(),
                )
            ]
        ]
    )


def _lang_toggle_keyboard(ru_url: str, en_url: str) -> InlineKeyboardMarkup:
    """Single toggle button that links to the other language version."""
    rows = []
    if ru_url and en_url:
        rows.append(
            [InlineKeyboardButton(text=vocab.BTN_LANG_TOGGLE, url=en_url)]
        )
    elif en_url:
        rows.append(
            [InlineKeyboardButton(text="🇬🇧 English", url=en_url)]
        )
    elif ru_url:
        rows.append(
            [InlineKeyboardButton(text="🇷🇺 Русский", url=ru_url)]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def _format_titles_message(titles: list[str], lang: str) -> str:
    header = vocab.MSG_CHOOSE_TITLE if lang == "ru" else vocab.MSG_CHOOSE_TITLE_EN
    lines = [header, ""]
    for i, title in enumerate(titles, 1):
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────────

@router.message(Command(vocab.CMD_START))
async def handle_start(message: Message) -> None:
    lang = _lang(message)
    await message.answer(
        vocab.MSG_WELCOME if lang == "ru" else vocab.MSG_WELCOME_EN
    )


@router.message(Command(vocab.CMD_HELP))
async def handle_help(message: Message) -> None:
    lang = _lang(message)
    await message.answer(
        vocab.MSG_HELP if lang == "ru" else vocab.MSG_HELP_EN
    )


@router.message(Command(vocab.CMD_REVIEW))
async def handle_review_command(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    # Check if URL is in the command args
    parts = text.split(maxsplit=1)
    if len(parts) > 1 and "arxiv" in parts[1]:
        await _start_pipeline(message, state)
    else:
        lang = _lang(message)
        await message.answer(
            vocab.MSG_SEND_URL if lang == "ru" else vocab.MSG_SEND_URL_EN
        )
        await state.set_state(ReviewStates.waiting_for_url)


# ── Direct URL handler (no /review needed) ────────────────────────────

@router.message(F.text.regexp(r"https?://(?:www\.)?arxiv\.org/"))
async def handle_direct_url(message: Message, state: FSMContext) -> None:
    """Handle arXiv URL sent directly without /review command."""
    await _start_pipeline(message, state)


@router.message(ReviewStates.waiting_for_url, F.text)
async def handle_review_url(message: Message, state: FSMContext) -> None:
    await _start_pipeline(message, state)


# ── Pipeline start ────────────────────────────────────────────────────

async def _start_pipeline(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    trigger_data = await _trigger.run(message, state)

    if not trigger_data.get("url"):
        await message.answer(
            vocab.MSG_INVALID_URL if lang == "ru" else vocab.MSG_INVALID_URL_EN
        )
        await state.clear()
        return

    url = trigger_data["url"]

    # Delete user's message and send status
    await _delete_safe(message)
    await state.update_data(_tracked_msgs=[])
    status_msg = await _send_and_track(
        message,
        vocab.MSG_PARSING if lang == "ru" else vocab.MSG_PARSING_EN,
        state,
    )
    await state.set_state(ReviewStates.parsing)

    try:
        parse_result = await _api.parse_article(url)
        parsed_article = parse_result.get("parsed_article", {})
        short_intro = parse_result.get("short_intro", "")
        abstract = parsed_article.get("abstract", "")

        titles = await _api.generate_titles(short_intro, abstract)
        if not titles:
            titles = ["Обзор статьи"]

        await state.update_data(
            source_url=url,
            parsed_article=parsed_article,
            short_intro=short_intro,
            abstract=abstract,
            titles=titles,
            chat_id=message.chat.id,
        )
        await state.set_state(ReviewStates.choosing_title)

        # Delete status, show titles
        await _delete_safe(status_msg)
        text = _format_titles_message(titles, lang)
        await _send_and_track(
            message, text, state, reply_markup=_titles_keyboard(titles)
        )

    except Exception as exc:
        logger.exception("Pipeline start failed for %s", url)
        await message.answer(
            (vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(
                error=str(exc)
            )
        )
        await state.clear()


# ── Title selection ───────────────────────────────────────────────────

@router.callback_query(TitleCallback.filter(F.action == "pick"))
async def handle_title_pick(
    callback: CallbackQuery, callback_data: TitleCallback, state: FSMContext
) -> None:
    lang = _lang(callback)
    data = await state.get_data()
    titles = data.get("titles", [])
    idx = callback_data.index - 1

    chosen = titles[idx] if 0 <= idx < len(titles) else titles[0] if titles else "Обзор"
    await state.update_data(chosen_title=chosen)
    await callback.answer()

    # Replace titles message with confirmation
    text = (
        vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN
    ).format(title=chosen)
    try:
        await callback.message.edit_text(text)
    except Exception:
        pass

    await _generate_and_show_cover(callback.message, state, lang)


@router.message(ReviewStates.choosing_title, F.text)
async def handle_typed_title(message: Message, state: FSMContext) -> None:
    """User typed text in title screen → use as title directly."""
    lang = _lang(message)
    chosen = message.text.strip()
    await state.update_data(chosen_title=chosen)

    # Delete user msg, cleanup tracked, show confirmation
    await _delete_safe(message)
    data = await state.get_data()
    await _cleanup_tracked(message.chat.id, state, message.bot)

    text = (
        vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN
    ).format(title=chosen)
    await _send_and_track(message, text, state)

    await _generate_and_show_cover(message, state, lang)


# ── Cover description ─────────────────────────────────────────────────

async def _generate_and_show_cover(
    message: Message, state: FSMContext, lang: str
) -> None:
    data = await state.get_data()
    try:
        cover_description = await _api.generate_cover_description(
            data.get("short_intro", "")
        )
        await state.update_data(cover_description=cover_description)
        await state.set_state(ReviewStates.viewing_cover_description)

        # Cleanup previous tracked messages
        await _cleanup_tracked(message.chat.id, state, message.bot)

        text = (
            vocab.MSG_COVER_DESCRIPTION
            if lang == "ru"
            else vocab.MSG_COVER_DESCRIPTION_EN
        ).format(description=cover_description)
        await _send_and_track(
            message, text, state, reply_markup=_cover_keyboard()
        )

    except Exception as exc:
        logger.exception("Cover description failed")
        await state.update_data(cover_description="")
        await _build_and_publish(message, state, lang)


@router.message(ReviewStates.viewing_cover_description, F.text)
async def handle_cover_text_input(message: Message, state: FSMContext) -> None:
    """User typed text in cover screen → edit description via LLM or replace."""
    lang = _lang(message)
    data = await state.get_data()
    current_desc = data.get("cover_description", "")
    user_text = message.text.strip()

    await _delete_safe(message)

    try:
        # If user text is long (>80 chars), treat as full replacement prompt
        if len(user_text) > 80:
            new_desc = user_text
        else:
            new_desc = await _api.edit_cover_description(current_desc, user_text)

        await state.update_data(cover_description=new_desc)
        await _cleanup_tracked(message.chat.id, state, message.bot)

        text = (
            vocab.MSG_COVER_DESCRIPTION
            if lang == "ru"
            else vocab.MSG_COVER_DESCRIPTION_EN
        ).format(description=new_desc)
        await _send_and_track(
            message, text, state, reply_markup=_cover_keyboard()
        )

    except Exception as exc:
        logger.exception("Cover edit failed")
        text = (
            vocab.MSG_COVER_DESCRIPTION
            if lang == "ru"
            else vocab.MSG_COVER_DESCRIPTION_EN
        ).format(description=current_desc)
        await _send_and_track(
            message, text, state, reply_markup=_cover_keyboard()
        )


@router.callback_query(CoverCallback.filter(F.action == "generate"))
async def handle_cover_generate(
    callback: CallbackQuery, state: FSMContext
) -> None:
    lang = _lang(callback)
    await callback.answer()
    data = await state.get_data()

    # Replace cover message with generating status
    try:
        await callback.message.edit_text(
            vocab.MSG_GENERATING_IMAGE
            if lang == "ru"
            else vocab.MSG_GENERATING_IMAGE_EN
        )
    except Exception:
        pass

    await state.set_state(ReviewStates.generating_image)

    try:
        from slugify import slugify

        chosen_title = data.get("chosen_title", "article")
        slug = slugify(chosen_title, max_length=80)
        cover_result = await _api.generate_cover(
            data.get("cover_description", ""), slug
        )
        await state.update_data(
            cover_url=cover_result.get("public_url", ""),
            slug=slug,
        )
    except Exception as exc:
        logger.exception("Cover generation failed")
        await state.update_data(cover_url="", slug="article")

    await _build_and_publish(callback.message, state, lang)


# ── Build & publish ───────────────────────────────────────────────────

async def _build_and_publish(
    message: Message, state: FSMContext, lang: str
) -> None:
    data = await state.get_data()
    chat_id = data.get("chat_id", message.chat.id)

    # Cleanup all intermediate messages
    await _cleanup_tracked(chat_id, state, message.bot)

    building_msg = await message.answer(
        vocab.MSG_BUILDING if lang == "ru" else vocab.MSG_BUILDING_EN
    )

    try:
        editorial = await _api.generate_editorial(
            data.get("parsed_article", {}),
            data.get("chosen_title", "Article Review"),
        )

        result = await _api.build_and_publish(
            title=data.get("chosen_title", editorial.get("title", "")),
            subtitle=editorial.get("subtitle", ""),
            article_body=editorial.get("article_body", ""),
            short_intro=data.get("short_intro", ""),
            cover_image_url=data.get("cover_url", ""),
            links=editorial.get("links", {}),
            figures=data.get("parsed_article", {}).get("figures", []),
            source_url=data.get("source_url", ""),
        )

        pages = result.get("pages", {})
        ru_url = pages.get("ru_html_url", "")
        en_url = pages.get("en_html_url", "")
        teaser = result.get("messages", {}).get("ru_telegram_text", "")

        # Delete building status
        await _delete_safe(building_msg)

        # ── Final message format ──
        # Title
        # Teaser paragraph
        # 📜 Полный обзор (hyperlink)
        title = data.get("chosen_title", "")
        link_url = ru_url or en_url

        text_parts = [f"<b>{title}</b>", ""]

        # Clean teaser (remove HTML bold tags if present from telegram_delivery)
        if teaser:
            # Strip existing title from teaser if it starts with <b>Title</b>
            clean_teaser = teaser
            if clean_teaser.startswith("<b>"):
                # Remove the first bold block (title) and following newlines
                import re
                clean_teaser = re.sub(
                    r"^<b>[^<]*</b>\s*\n*", "", clean_teaser
                ).strip()
            # Remove trailing link text
            clean_teaser = re.sub(
                r'<a href="[^"]*">[^<]*</a>.*$',
                "",
                clean_teaser,
                flags=re.DOTALL,
            ).strip()
            if clean_teaser:
                text_parts.append(clean_teaser)
                text_parts.append("")

        if link_url:
            text_parts.append(f'📜 <a href="{link_url}">Полный обзор</a>')

        # One button to toggle language
        keyboard = _lang_toggle_keyboard(ru_url, en_url)

        await message.answer(
            "\n".join(text_parts),
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )

    except Exception as exc:
        logger.exception("Build and publish failed")
        await _delete_safe(building_msg)
        await message.answer(
            (vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(
                error=str(exc)
            )
        )

    await state.clear()
