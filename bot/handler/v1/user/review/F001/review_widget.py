"""
Widget: Interactive arXiv Review Pipeline.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001, SC002, SC005, SC011, SC012

Flow:
1. /review <url> or send URL → parse article → generate 10 titles
2. User picks title (button 1-10) or types custom → regenerate titles
3. Show cover description → user edits or generates
4. Build & publish → show result with RU/EN links
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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


def _lang(event) -> str:
    user = event.from_user if hasattr(event, 'from_user') else None
    if user:
        lc = user.language_code or "ru"
        return "ru" if lc.startswith("ru") else "en"
    return "ru"


def _titles_keyboard(titles: list[str]) -> InlineKeyboardMarkup:
    """Build inline keyboard with numbered title buttons + custom button."""
    buttons = []
    # Two rows of 5 buttons
    row1 = [InlineKeyboardButton(text=str(i+1), callback_data=TitleCallback(action="pick", index=i+1).pack()) for i in range(min(5, len(titles)))]
    row2 = [InlineKeyboardButton(text=str(i+1), callback_data=TitleCallback(action="pick", index=i+1).pack()) for i in range(5, min(10, len(titles)))]
    if row1:
        buttons.append(row1)
    if row2:
        buttons.append(row2)
    buttons.append([InlineKeyboardButton(text=vocab.BTN_CUSTOM_TITLE, callback_data=TitleCallback(action="custom", index=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _cover_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for cover description actions."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=vocab.BTN_EDIT_COVER, callback_data=CoverCallback(action="edit").pack()),
            InlineKeyboardButton(text=vocab.BTN_GENERATE_COVER, callback_data=CoverCallback(action="generate").pack()),
        ]
    ])


def _format_titles_message(titles: list[str], lang: str) -> str:
    """Format the titles list as a numbered message."""
    header = vocab.MSG_CHOOSE_TITLE if lang == "ru" else vocab.MSG_CHOOSE_TITLE_EN
    lines = [header, ""]
    for i, title in enumerate(titles, 1):
        lines.append(f"{i}. {title}")
    return "\n".join(lines)


# ── Command handlers ──────────────────────────────────────────────

@router.message(Command(vocab.CMD_START))
async def handle_start(message: Message) -> None:
    lang = _lang(message)
    await message.answer(vocab.MSG_WELCOME if lang == "ru" else vocab.MSG_WELCOME_EN)

@router.message(Command(vocab.CMD_HELP))
async def handle_help(message: Message) -> None:
    lang = _lang(message)
    await message.answer(vocab.MSG_HELP if lang == "ru" else vocab.MSG_HELP_EN)

@router.message(Command(vocab.CMD_REVIEW))
async def handle_review_command(message: Message, state: FSMContext) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        await _start_pipeline(message, state)
    else:
        lang = _lang(message)
        await message.answer(vocab.MSG_SEND_URL if lang == "ru" else vocab.MSG_SEND_URL_EN)
        await state.set_state(ReviewStates.waiting_for_url)

@router.message(ReviewStates.waiting_for_url, F.text)
async def handle_review_url(message: Message, state: FSMContext) -> None:
    await _start_pipeline(message, state)


async def _start_pipeline(message: Message, state: FSMContext) -> None:
    """Parse article and show title options."""
    lang = _lang(message)
    trigger_data = await _trigger.run(message, state)

    if not trigger_data.get("url"):
        await message.answer(vocab.MSG_INVALID_URL if lang == "ru" else vocab.MSG_INVALID_URL_EN)
        await state.clear()
        return

    url = trigger_data["url"]
    await message.answer(vocab.MSG_PARSING if lang == "ru" else vocab.MSG_PARSING_EN)
    await state.set_state(ReviewStates.parsing)

    try:
        # Step 1: Parse article
        parse_result = await _api.parse_article(url)
        parsed_article = parse_result.get("parsed_article", {})
        short_intro = parse_result.get("short_intro", "")
        abstract = parsed_article.get("abstract", "")

        # Step 2: Generate 10 titles
        titles = await _api.generate_titles(short_intro, abstract)

        if not titles:
            titles = ["Обзор статьи"]  # fallback

        # Save state data
        await state.update_data(
            source_url=url,
            parsed_article=parsed_article,
            short_intro=short_intro,
            abstract=abstract,
            titles=titles,
        )
        await state.set_state(ReviewStates.choosing_title)

        # Show titles
        text = _format_titles_message(titles, lang)
        await message.answer(text, reply_markup=_titles_keyboard(titles))

    except Exception as exc:
        logger.exception("Pipeline parse/titles failed for %s", url)
        error_text = vocab.MSG_ERROR.format(error=str(exc)) if lang == "ru" else vocab.MSG_ERROR_EN.format(error=str(exc))
        await message.answer(error_text)
        await state.clear()


# ── Title selection ───────────────────────────────────────────────

@router.callback_query(TitleCallback.filter(F.action == "pick"))
async def handle_title_pick(callback: CallbackQuery, callback_data: TitleCallback, state: FSMContext) -> None:
    lang = _lang(callback)
    data = await state.get_data()
    titles = data.get("titles", [])
    index = callback_data.index - 1

    if 0 <= index < len(titles):
        chosen_title = titles[index]
    else:
        chosen_title = titles[0] if titles else "Обзор статьи"

    await state.update_data(chosen_title=chosen_title)
    await callback.answer()

    # Confirm selection and proceed to cover
    text = (vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=chosen_title)
    await callback.message.edit_text(text)

    await _generate_and_show_cover(callback.message, state, lang, data)


@router.callback_query(TitleCallback.filter(F.action == "custom"))
async def handle_title_custom(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    await callback.answer()
    await state.set_state(ReviewStates.typing_custom_title)
    text = vocab.MSG_SEND_CUSTOM_TITLE if lang == "ru" else vocab.MSG_SEND_CUSTOM_TITLE_EN
    await callback.message.edit_text(text)


@router.message(ReviewStates.typing_custom_title, F.text)
async def handle_custom_title_input(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    custom_title = message.text.strip()
    data = await state.get_data()

    await message.answer(vocab.MSG_REGENERATING_TITLES if lang == "ru" else vocab.MSG_REGENERATING_TITLES_EN)

    try:
        titles = await _api.regenerate_titles(
            custom_title, data.get("short_intro", ""), data.get("abstract", "")
        )
        if not titles:
            titles = [custom_title]

        await state.update_data(titles=titles)
        await state.set_state(ReviewStates.choosing_title)

        text = _format_titles_message(titles, lang)
        await message.answer(text, reply_markup=_titles_keyboard(titles))

    except Exception as exc:
        logger.exception("Title regeneration failed")
        # Fallback: just use the custom title
        await state.update_data(chosen_title=custom_title)
        text = (vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=custom_title)
        await message.answer(text)
        await _generate_and_show_cover(message, state, lang, data)


# ── Cover description ─────────────────────────────────────────────

async def _generate_and_show_cover(message: Message, state: FSMContext, lang: str, data: dict) -> None:
    """Generate cover description and show to user."""
    try:
        short_intro = data.get("short_intro", "")
        cover_description = await _api.generate_cover_description(short_intro)
        await state.update_data(cover_description=cover_description)
        await state.set_state(ReviewStates.viewing_cover_description)

        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=cover_description)
        await message.answer(text, reply_markup=_cover_keyboard())

    except Exception as exc:
        logger.exception("Cover description generation failed")
        # Proceed without cover
        await state.update_data(cover_description="")
        await _build_and_publish(message, state, lang)


@router.callback_query(CoverCallback.filter(F.action == "edit"))
async def handle_cover_edit(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    await callback.answer()
    await state.set_state(ReviewStates.typing_cover_edit)
    text = vocab.MSG_SEND_COVER_EDIT if lang == "ru" else vocab.MSG_SEND_COVER_EDIT_EN
    await callback.message.edit_text(text)


@router.message(ReviewStates.typing_cover_edit, F.text)
async def handle_cover_edit_input(message: Message, state: FSMContext) -> None:
    lang = _lang(message)
    data = await state.get_data()
    current_desc = data.get("cover_description", "")

    try:
        new_desc = await _api.edit_cover_description(current_desc, message.text.strip())
        await state.update_data(cover_description=new_desc)
        await state.set_state(ReviewStates.viewing_cover_description)

        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=new_desc)
        await message.answer(text, reply_markup=_cover_keyboard())

    except Exception as exc:
        logger.exception("Cover edit failed")
        await state.set_state(ReviewStates.viewing_cover_description)
        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=current_desc)
        await message.answer(text, reply_markup=_cover_keyboard())


@router.callback_query(CoverCallback.filter(F.action == "generate"))
async def handle_cover_generate(callback: CallbackQuery, state: FSMContext) -> None:
    lang = _lang(callback)
    await callback.answer()
    data = await state.get_data()

    await callback.message.edit_text(vocab.MSG_GENERATING_IMAGE if lang == "ru" else vocab.MSG_GENERATING_IMAGE_EN)
    await state.set_state(ReviewStates.generating_image)

    try:
        from slugify import slugify
        chosen_title = data.get("chosen_title", "article")
        slug = slugify(chosen_title, max_length=80)
        cover_result = await _api.generate_cover(data.get("cover_description", ""), slug)
        await state.update_data(
            cover_url=cover_result.get("public_url", ""),
            slug=slug,
        )
    except Exception as exc:
        logger.exception("Cover generation failed")
        await state.update_data(cover_url="", slug="article")

    await _build_and_publish(callback.message, state, lang)


async def _build_and_publish(message: Message, state: FSMContext, lang: str) -> None:
    """Build HTML pages and publish."""
    data = await state.get_data()
    await message.answer(vocab.MSG_BUILDING if lang == "ru" else vocab.MSG_BUILDING_EN)
    await state.set_state(ReviewStates.building)

    try:
        # First generate the editorial article
        editorial = await _api.generate_editorial(
            data.get("parsed_article", {}),
            data.get("chosen_title", "Article Review"),
        )

        # Build and publish
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

        # Build result message (text links — no inline URL buttons
        # because Telegram requires HTTPS for button URLs)
        title = data.get("chosen_title", "")
        text_parts = [f"✅ <b>{title}</b>"]
        if teaser and "<b>" not in teaser:
            text_parts.append(f"\n{teaser}")
        text_parts.append("")

        if ru_url:
            text_parts.append(f'🇷🇺 <a href="{ru_url}">Читать статью (RU)</a>')
        if en_url:
            text_parts.append(f'🇬🇧 <a href="{en_url}">Read in English (EN)</a>')

        await message.answer("\n".join(text_parts), disable_web_page_preview=False)

    except Exception as exc:
        logger.exception("Build and publish failed")
        error_text = vocab.MSG_ERROR.format(error=str(exc)) if lang == "ru" else vocab.MSG_ERROR_EN.format(error=str(exc))
        await message.answer(error_text)

    await state.clear()
