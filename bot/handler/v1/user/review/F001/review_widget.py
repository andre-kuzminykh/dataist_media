"""
Widget: Interactive arXiv Review Pipeline.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001, SC002, SC005, SC011, SC012, SC013, SC014

Flow:
1. Send arXiv URL (no /review needed) → parse → 10 titles
2. Button 1-10 = pick title. Text = regenerate titles. "Ввести своё" → type = use as title
3. Show cover description (short, visual). Text = LLM edits. "Ввести своё" → type = replace.
   🖼 Сгенерировать = generate image
4. Final: title + teaser + "📜 Полный обзор" hyperlink + [🔄 EN/RU] button
5. All intermediate messages deleted, only final remains
"""

import logging
import re

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


async def _del(msg: Message) -> None:
    try:
        await msg.delete()
    except Exception:
        pass


async def _track(target: Message, text: str, state: FSMContext, **kw) -> Message:
    """Send message and track its id for later deletion."""
    sent = await target.answer(text, **kw)
    data = await state.get_data()
    tracked: list[int] = data.get("_msgs", [])
    tracked.append(sent.message_id)
    await state.update_data(_msgs=tracked)
    return sent


async def _cleanup(chat_id: int, state: FSMContext, bot) -> None:
    """Delete all tracked messages."""
    data = await state.get_data()
    for mid in data.get("_msgs", []):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(_msgs=[])


def _titles_kb(titles: list[str]) -> InlineKeyboardMarkup:
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
    rows.append([
        InlineKeyboardButton(
            text="✏️ Ввести своё",
            callback_data=TitleCallback(action="custom", index=0).pack(),
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cover_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Ввести своё",
                callback_data=CoverCallback(action="custom").pack(),
            ),
            InlineKeyboardButton(
                text=vocab.BTN_GENERATE_COVER,
                callback_data=CoverCallback(action="generate").pack(),
            ),
        ]
    ])


def _lang_kb(ru_url: str, en_url: str) -> InlineKeyboardMarkup | None:
    if ru_url and en_url:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 EN / RU", url=en_url)]
        ])
    if en_url:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇬🇧 English", url=en_url)]
        ])
    if ru_url:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Русский", url=ru_url)]
        ])
    return None


def _fmt_titles(titles: list[str], lang: str) -> str:
    h = vocab.MSG_CHOOSE_TITLE if lang == "ru" else vocab.MSG_CHOOSE_TITLE_EN
    lines = [h, ""]
    for i, t in enumerate(titles, 1):
        lines.append(f"{i}. {t}")
    return "\n".join(lines)


# ── Commands ──────────────────────────────────────────────────────────

@router.message(Command(vocab.CMD_START))
async def h_start(message: Message) -> None:
    lang = _lang(message)
    await message.answer(vocab.MSG_WELCOME if lang == "ru" else vocab.MSG_WELCOME_EN)


@router.message(Command(vocab.CMD_HELP))
async def h_help(message: Message) -> None:
    lang = _lang(message)
    await message.answer(vocab.MSG_HELP if lang == "ru" else vocab.MSG_HELP_EN)


@router.message(Command(vocab.CMD_REVIEW))
async def h_review(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1 and "arxiv" in parts[1]:
        await _start(message, state)
    else:
        lang = _lang(message)
        await message.answer(vocab.MSG_SEND_URL if lang == "ru" else vocab.MSG_SEND_URL_EN)
        await state.set_state(ReviewStates.waiting_for_url)


@router.message(F.text.regexp(r"https?://(?:www\.)?arxiv\.org/"))
async def h_direct_url(message: Message, state: FSMContext) -> None:
    await _start(message, state)


@router.message(ReviewStates.waiting_for_url, F.text)
async def h_waiting_url(message: Message, state: FSMContext) -> None:
    await _start(message, state)


# ── Pipeline start ────────────────────────────────────────────────────

async def _start(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    trigger_data = await _trigger.run(message, state)

    if not trigger_data.get("url"):
        await message.answer(vocab.MSG_INVALID_URL if lang == "ru" else vocab.MSG_INVALID_URL_EN)
        await state.clear()
        return

    url = trigger_data["url"]
    await _del(message)
    await state.update_data(_msgs=[], chat_id=message.chat.id)
    status = await _track(message, vocab.MSG_PARSING if lang == "ru" else vocab.MSG_PARSING_EN, state)
    await state.set_state(ReviewStates.parsing)

    try:
        parse_result = await _api.parse_article(url)
        parsed = parse_result.get("parsed_article", {})
        short_intro = parse_result.get("short_intro", "")
        abstract = parsed.get("abstract", "")

        titles = await _api.generate_titles(short_intro, abstract)
        if not titles:
            titles = ["Обзор статьи"]

        await state.update_data(
            source_url=url, parsed_article=parsed,
            short_intro=short_intro, abstract=abstract, titles=titles,
        )
        await state.set_state(ReviewStates.choosing_title)

        await _del(status)
        await _track(message, _fmt_titles(titles, lang), state, reply_markup=_titles_kb(titles))

    except Exception as exc:
        logger.exception("Start failed for %s", url)
        await message.answer(
            (vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(error=str(exc))
        )
        await state.clear()


# ── Title: button pick ────────────────────────────────────────────────

@router.callback_query(TitleCallback.filter(F.action == "pick"))
async def h_title_pick(cb: CallbackQuery, callback_data: TitleCallback, state: FSMContext) -> None:
    lang = _lang(cb)
    data = await state.get_data()
    titles = data.get("titles", [])
    idx = callback_data.index - 1
    chosen = titles[idx] if 0 <= idx < len(titles) else titles[0] if titles else "Обзор"
    await state.update_data(chosen_title=chosen)
    await cb.answer()
    try:
        await cb.message.edit_text(
            (vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=chosen)
        )
    except Exception:
        pass
    await _show_cover(cb.message, state, lang)


# ── Title: text input = regenerate titles ─────────────────────────────

@router.message(ReviewStates.choosing_title, F.text)
async def h_title_text(message: Message, state: FSMContext) -> None:
    """Text typed on title screen → regenerate titles based on this text."""
    lang = _lang(message)
    user_text = message.text.strip()
    data = await state.get_data()
    await _del(message)

    try:
        titles = await _api.regenerate_titles(user_text, data.get("short_intro", ""), data.get("abstract", ""))
        if not titles:
            titles = [user_text]
        await state.update_data(titles=titles)
        await _cleanup(message.chat.id, state, message.bot)
        await _track(message, _fmt_titles(titles, lang), state, reply_markup=_titles_kb(titles))
    except Exception:
        logger.exception("Title regeneration failed")
        await state.update_data(chosen_title=user_text)
        await _cleanup(message.chat.id, state, message.bot)
        await _show_cover(message, state, lang)


# ── Title: "Ввести своё" button → direct input ───────────────────────

@router.callback_query(TitleCallback.filter(F.action == "custom"))
async def h_title_custom_btn(cb: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(cb)
    await cb.answer()
    await state.set_state(ReviewStates.typing_custom_title)
    try:
        await cb.message.edit_text("✏️ Введите свой заголовок:" if lang == "ru" else "✏️ Type your title:")
    except Exception:
        pass


@router.message(ReviewStates.typing_custom_title, F.text)
async def h_title_custom_input(message: Message, state: FSMContext) -> None:
    """Text after 'Ввести своё' → use as title directly."""
    lang = _lang(message)
    chosen = message.text.strip()
    await state.update_data(chosen_title=chosen)
    await _del(message)
    await _cleanup(message.chat.id, state, message.bot)
    await _track(
        message,
        (vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=chosen),
        state,
    )
    await _show_cover(message, state, lang)


# ── Cover description ─────────────────────────────────────────────────

async def _show_cover(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    try:
        desc = await _api.generate_cover_description(data.get("short_intro", ""))
        await state.update_data(cover_description=desc)
        await state.set_state(ReviewStates.viewing_cover_description)
        await _cleanup(message.chat.id, state, message.bot)

        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=desc)
        await _track(message, text, state, reply_markup=_cover_kb())
    except Exception as exc:
        logger.exception("Cover description failed")
        await state.update_data(cover_description="")
        await _build(message, state, lang)


# ── Cover: text input = LLM edits description ────────────────────────

@router.message(ReviewStates.viewing_cover_description, F.text)
async def h_cover_text(message: Message, state: FSMContext) -> None:
    """Text on cover screen → LLM edits current description."""
    lang = _lang(message)
    data = await state.get_data()
    current = data.get("cover_description", "")
    user_text = message.text.strip()
    await _del(message)

    try:
        new_desc = await _api.edit_cover_description(current, user_text)
        await state.update_data(cover_description=new_desc)
        await _cleanup(message.chat.id, state, message.bot)
        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=new_desc)
        await _track(message, text, state, reply_markup=_cover_kb())
    except Exception:
        logger.exception("Cover edit failed")
        await _cleanup(message.chat.id, state, message.bot)
        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=current)
        await _track(message, text, state, reply_markup=_cover_kb())


# ── Cover: "Ввести своё" → replace description entirely ──────────────

@router.callback_query(CoverCallback.filter(F.action == "custom"))
async def h_cover_custom_btn(cb: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(cb)
    await cb.answer()
    await state.set_state(ReviewStates.typing_cover_edit)
    try:
        await cb.message.edit_text("✏️ Введите своё описание обложки:" if lang == "ru" else "✏️ Type your cover description:")
    except Exception:
        pass


@router.message(ReviewStates.typing_cover_edit, F.text)
async def h_cover_custom_input(message: Message, state: FSMContext) -> None:
    """Text after 'Ввести своё' → replace cover description entirely."""
    lang = _lang(message)
    new_desc = message.text.strip()
    await state.update_data(cover_description=new_desc)
    await state.set_state(ReviewStates.viewing_cover_description)
    await _del(message)
    await _cleanup(message.chat.id, state, message.bot)
    text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=new_desc)
    await _track(message, text, state, reply_markup=_cover_kb())


# ── Cover: generate image ────────────────────────────────────────────

@router.callback_query(CoverCallback.filter(F.action == "generate"))
async def h_cover_gen(cb: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(cb)
    await cb.answer()
    data = await state.get_data()

    try:
        await cb.message.edit_text(vocab.MSG_GENERATING_IMAGE if lang == "ru" else vocab.MSG_GENERATING_IMAGE_EN)
    except Exception:
        pass
    await state.set_state(ReviewStates.generating_image)

    try:
        from slugify import slugify
        slug = slugify(data.get("chosen_title", "article"), max_length=80)
        cover_result = await _api.generate_cover(data.get("cover_description", ""), slug)
        await state.update_data(cover_url=cover_result.get("public_url", ""), slug=slug)
    except Exception:
        logger.exception("Cover generation failed")
        await state.update_data(cover_url="", slug="article")

    await _build(cb.message, state, lang)


# ── Build & publish ───────────────────────────────────────────────────

async def _build(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    chat_id = data.get("chat_id", message.chat.id)
    await _cleanup(chat_id, state, message.bot)

    building_msg = await message.answer(vocab.MSG_BUILDING if lang == "ru" else vocab.MSG_BUILDING_EN)

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

        await _del(building_msg)

        # ── Format final message ──
        title = data.get("chosen_title", "")
        link_url = ru_url or en_url

        parts = [f"<b>{title}</b>", ""]

        # Clean teaser: remove title block and trailing links
        if teaser:
            clean = re.sub(r"^<b>[^<]*</b>\s*\n*", "", teaser).strip()
            clean = re.sub(r'<a href="[^"]*">[^<]*</a>.*$', "", clean, flags=re.DOTALL).strip()
            if clean:
                parts.append(clean)
                parts.append("")

        if link_url:
            parts.append(f'📜 <a href="{link_url}">Полный обзор</a>')

        await message.answer(
            "\n".join(parts),
            reply_markup=_lang_kb(ru_url, en_url),
            disable_web_page_preview=False,
        )

    except Exception as exc:
        logger.exception("Build and publish failed")
        await _del(building_msg)
        await message.answer(
            (vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(error=str(exc))
        )

    await state.clear()
