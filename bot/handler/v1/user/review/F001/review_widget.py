"""
Widget: Interactive arXiv Review Pipeline.

## Traceability
Feature: F001, F002
Scenarios: SC001, SC002, SC005, SC011-SC014

Flow:
1. Send arXiv URL (no /review needed) → parse → 10 titles
2. Button 1-10 = pick. Text = regenerate. "Ввести своё" → type = use directly
3. Cover description (short visual). Text = LLM edit. "Ввести своё" → replace.
4. 🖼 Сгенерировать → show image → text = edit+regenerate, ✅ = approve
5. Final: title + teaser + "📜 Полный обзор" hyperlink + inline [🔄 EN/RU] callback
6. All intermediate msgs deleted. Lang toggle switches message content.
"""

import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext

from bot.core import vocab
from bot.state.review_state import ReviewStates
from bot.callback.review_callback import TitleCallback, CoverCallback, LangCallback
from bot.service.api.pipeline_api import PipelineAPI
from bot.node.review.trigger.review_trigger import ReviewTrigger

logger = logging.getLogger(__name__)
router = Router(name="review_widget")
_trigger = ReviewTrigger()
_api = PipelineAPI()

# Cache for final messages (survives state.clear)
_final_cache: dict[int, dict] = {}  # chat_id → {ru_text, en_text}


# ── Helpers ───────────────────────────────────────────────────────────

def _lang(event) -> str:
    user = getattr(event, "from_user", None)
    if user:
        lc = user.language_code or "ru"
        return "ru" if lc.startswith("ru") else "en"
    return "ru"


async def _del(msg):
    try:
        await msg.delete()
    except Exception:
        pass


async def _send(target, text, state, **kw):
    sent = await target.answer(text, **kw)
    data = await state.get_data()
    tracked = data.get("_m", [])
    tracked.append(sent.message_id)
    await state.update_data(_m=tracked)
    return sent


async def _clean(chat_id, state, bot):
    data = await state.get_data()
    for mid in data.get("_m", []):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    await state.update_data(_m=[])


async def _send_cover_photo(target: Message, cover_url: str, caption: str,
                            state: FSMContext, reply_markup=None) -> Message | None:
    """Download cover from service and send as Telegram photo."""
    image_data = await _api.download_cover_image(cover_url)
    if image_data:
        photo = BufferedInputFile(image_data, filename="cover.png")
        sent = await target.answer_photo(
            photo, caption=caption, reply_markup=reply_markup, parse_mode="HTML"
        )
        data = await state.get_data()
        tracked = data.get("_m", [])
        tracked.append(sent.message_id)
        await state.update_data(_m=tracked)
        return sent
    # Fallback: just send text
    return await _send(target, caption, state, reply_markup=reply_markup)


def _titles_kb(titles):
    r1 = [InlineKeyboardButton(text=str(i+1), callback_data=TitleCallback(action="pick", index=i+1).pack()) for i in range(min(5, len(titles)))]
    r2 = [InlineKeyboardButton(text=str(i+1), callback_data=TitleCallback(action="pick", index=i+1).pack()) for i in range(5, min(10, len(titles)))]
    rows = []
    if r1: rows.append(r1)
    if r2: rows.append(r2)
    rows.append([InlineKeyboardButton(text="✏️ Ввести своё", callback_data=TitleCallback(action="custom", index=0).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _cover_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️ Ввести своё", callback_data=CoverCallback(action="custom").pack()),
        InlineKeyboardButton(text=vocab.BTN_GENERATE_COVER, callback_data=CoverCallback(action="generate").pack()),
    ]])


def _image_review_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Утвердить", callback_data=CoverCallback(action="approve").pack()),
    ]])


def _lang_toggle_kb(show_next: str = "en"):
    """Inline callback button to switch RU/EN — NOT a URL button."""
    label = "🇬🇧 English" if show_next == "en" else "🇷🇺 Русский"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=label, callback_data=LangCallback(show=show_next).pack()),
    ]])


def _fmt_titles(titles, lang):
    h = vocab.MSG_CHOOSE_TITLE if lang == "ru" else vocab.MSG_CHOOSE_TITLE_EN
    lines = [h, ""]
    for i, t in enumerate(titles, 1):
        lines.append(f"{i}. {t}")
    return "\n".join(lines)


def _fmt_final(title, teaser_raw, link_url):
    """Format final message: title + clean teaser + hyperlink."""
    parts = [f"<b>{title}</b>", ""]
    if teaser_raw:
        clean = re.sub(r"^<b>[^<]*</b>\s*\n*", "", teaser_raw).strip()
        clean = re.sub(r'<a href="[^"]*">[^<]*</a>.*$', "", clean, flags=re.DOTALL).strip()
        if clean:
            parts.append(clean)
            parts.append("")
    if link_url:
        parts.append(f"📜 Полный обзор:\n{link_url}")
    return "\n".join(parts)


# ── Commands ──────────────────────────────────────────────────────────

@router.message(Command(vocab.CMD_START))
async def h_start(m: Message):
    await m.answer(vocab.MSG_WELCOME if _lang(m) == "ru" else vocab.MSG_WELCOME_EN)

@router.message(Command(vocab.CMD_HELP))
async def h_help(m: Message):
    await m.answer(vocab.MSG_HELP if _lang(m) == "ru" else vocab.MSG_HELP_EN)

@router.message(Command(vocab.CMD_REVIEW))
async def h_review(m: Message, state: FSMContext):
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) > 1 and "arxiv" in parts[1]:
        await _start(m, state)
    else:
        await m.answer(vocab.MSG_SEND_URL if _lang(m) == "ru" else vocab.MSG_SEND_URL_EN)
        await state.set_state(ReviewStates.waiting_for_url)

@router.message(F.text.regexp(r"https?://(?:www\.)?arxiv\.org/"))
async def h_direct(m: Message, state: FSMContext):
    await _start(m, state)

@router.message(ReviewStates.waiting_for_url, F.text)
async def h_wait(m: Message, state: FSMContext):
    await _start(m, state)


# ── Pipeline start ────────────────────────────────────────────────────

async def _start(m: Message, state: FSMContext):
    lang = _lang(m)
    td = await _trigger.run(m, state)
    if not td.get("url"):
        await m.answer(vocab.MSG_INVALID_URL if lang == "ru" else vocab.MSG_INVALID_URL_EN)
        await state.clear()
        return

    url = td["url"]
    await _del(m)
    await state.update_data(_m=[], chat_id=m.chat.id)
    status = await _send(m, vocab.MSG_PARSING if lang == "ru" else vocab.MSG_PARSING_EN, state)
    await state.set_state(ReviewStates.parsing)

    try:
        pr = await _api.parse_article(url)
        parsed = pr.get("parsed_article", {})
        si = pr.get("short_intro", "")
        ab = parsed.get("abstract", "")
        titles = await _api.generate_titles(si, ab) or ["Обзор статьи"]

        await state.update_data(source_url=url, parsed_article=parsed, short_intro=si, abstract=ab, titles=titles)
        await state.set_state(ReviewStates.choosing_title)
        await _del(status)
        await _send(m, _fmt_titles(titles, lang), state, reply_markup=_titles_kb(titles))
    except Exception as e:
        logger.exception("Start failed")
        await m.answer((vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(error=str(e)))
        await state.clear()


# ── Title: pick ───────────────────────────────────────────────────────

@router.callback_query(TitleCallback.filter(F.action == "pick"))
async def h_tpick(cb: CallbackQuery, callback_data: TitleCallback, state: FSMContext):
    lang = _lang(cb)
    data = await state.get_data()
    titles = data.get("titles", [])
    idx = callback_data.index - 1
    chosen = titles[idx] if 0 <= idx < len(titles) else titles[0] if titles else "Обзор"
    await state.update_data(chosen_title=chosen)
    await cb.answer()
    try:
        await cb.message.edit_text((vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=chosen))
    except Exception:
        pass
    await _show_cover(cb.message, state, lang)


# ── Title: text = regenerate ──────────────────────────────────────────

@router.message(ReviewStates.choosing_title, F.text)
async def h_ttext(m: Message, state: FSMContext):
    lang = _lang(m)
    txt = m.text.strip()
    data = await state.get_data()
    await _del(m)
    try:
        titles = await _api.regenerate_titles(txt, data.get("short_intro", ""), data.get("abstract", "")) or [txt]
        await state.update_data(titles=titles)
        await _clean(m.chat.id, state, m.bot)
        await _send(m, _fmt_titles(titles, lang), state, reply_markup=_titles_kb(titles))
    except Exception:
        logger.exception("Regen failed")
        await state.update_data(chosen_title=txt)
        await _clean(m.chat.id, state, m.bot)
        await _show_cover(m, state, lang)


# ── Title: "Ввести своё" ─────────────────────────────────────────────

@router.callback_query(TitleCallback.filter(F.action == "custom"))
async def h_tcustom(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(ReviewStates.typing_custom_title)
    try:
        await cb.message.edit_text("✏️ Введите свой заголовок:" if _lang(cb) == "ru" else "✏️ Type your title:")
    except Exception:
        pass

@router.message(ReviewStates.typing_custom_title, F.text)
async def h_tcustom_in(m: Message, state: FSMContext):
    lang = _lang(m)
    chosen = m.text.strip()
    await state.update_data(chosen_title=chosen)
    await _del(m)
    await _clean(m.chat.id, state, m.bot)
    await _send(m, (vocab.MSG_TITLE_SELECTED if lang == "ru" else vocab.MSG_TITLE_SELECTED_EN).format(title=chosen), state)
    await _show_cover(m, state, lang)


# ── Cover description ─────────────────────────────────────────────────

async def _show_cover(msg, state, lang):
    data = await state.get_data()
    try:
        desc = await _api.generate_cover_description(data.get("short_intro", ""))
        await state.update_data(cover_description=desc)
        await state.set_state(ReviewStates.viewing_cover_description)
        await _clean(msg.chat.id, state, msg.bot)
        text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=desc)
        await _send(msg, text, state, reply_markup=_cover_kb())
    except Exception:
        logger.exception("Cover desc failed")
        await state.update_data(cover_description="")
        await _build(msg, state, lang)


# ── Cover: text = LLM edit ───────────────────────────────────────────

@router.message(ReviewStates.viewing_cover_description, F.text)
async def h_ctext(m: Message, state: FSMContext):
    lang = _lang(m)
    data = await state.get_data()
    cur = data.get("cover_description", "")
    await _del(m)
    try:
        new = await _api.edit_cover_description(cur, m.text.strip())
        await state.update_data(cover_description=new)
    except Exception:
        new = cur
    await _clean(m.chat.id, state, m.bot)
    text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=new)
    await _send(m, text, state, reply_markup=_cover_kb())


# ── Cover: "Ввести своё" → replace ───────────────────────────────────

@router.callback_query(CoverCallback.filter(F.action == "custom"))
async def h_ccustom(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(ReviewStates.typing_cover_edit)
    try:
        await cb.message.edit_text("✏️ Введите описание обложки:" if _lang(cb) == "ru" else "✏️ Type cover description:")
    except Exception:
        pass

@router.message(ReviewStates.typing_cover_edit, F.text)
async def h_ccustom_in(m: Message, state: FSMContext):
    lang = _lang(m)
    new = m.text.strip()
    await state.update_data(cover_description=new)
    await state.set_state(ReviewStates.viewing_cover_description)
    await _del(m)
    await _clean(m.chat.id, state, m.bot)
    text = (vocab.MSG_COVER_DESCRIPTION if lang == "ru" else vocab.MSG_COVER_DESCRIPTION_EN).format(description=new)
    await _send(m, text, state, reply_markup=_cover_kb())


# ── Cover: generate image → show for review ──────────────────────────

@router.callback_query(CoverCallback.filter(F.action == "generate"))
async def h_cgen(cb: CallbackQuery, state: FSMContext):
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
        cover = await _api.generate_cover(data.get("cover_description", ""), slug)
        cover_url = cover.get("public_url", "")
        await state.update_data(cover_url=cover_url, slug=slug)
    except Exception:
        logger.exception("Cover gen failed")
        cover_url = ""
        await state.update_data(cover_url="", slug="article")

    # Show generated image for review
    await _clean(cb.message.chat.id, state, cb.message.bot)
    await state.set_state(ReviewStates.reviewing_image)

    if cover_url:
        caption = "🖼 <b>Обложка готова</b>\n\nНапишите правки или нажмите ✅ Утвердить"
        await _send_cover_photo(cb.message, cover_url, caption, state, reply_markup=_image_review_kb())
    else:
        await _send(cb.message, "⚠️ Не удалось сгенерировать. Нажмите ✅ чтобы продолжить.", state, reply_markup=_image_review_kb())


# ── Image review: text = edit description + regenerate ────────────────

@router.message(ReviewStates.reviewing_image, F.text)
async def h_img_text(m: Message, state: FSMContext):
    """User sends text edits → update description and regenerate image."""
    lang = _lang(m)
    data = await state.get_data()
    cur = data.get("cover_description", "")
    await _del(m)

    try:
        new_desc = await _api.edit_cover_description(cur, m.text.strip())
        await state.update_data(cover_description=new_desc)
    except Exception:
        new_desc = m.text.strip()
        await state.update_data(cover_description=new_desc)

    # Regenerate image with new description
    await _clean(m.chat.id, state, m.bot)
    gen_msg = await _send(m, vocab.MSG_GENERATING_IMAGE if lang == "ru" else vocab.MSG_GENERATING_IMAGE_EN, state)

    try:
        from slugify import slugify
        slug = data.get("slug", slugify(data.get("chosen_title", "article"), max_length=80))
        prev_cover = data.get("cover_url", "")
        cover = await _api.generate_cover(new_desc, slug, previous_cover_url=prev_cover)
        cover_url = cover.get("public_url", "")
        await state.update_data(cover_url=cover_url)
    except Exception:
        cover_url = ""
        await state.update_data(cover_url="")

    await _clean(m.chat.id, state, m.bot)

    if cover_url:
        caption = "🖼 <b>Обложка обновлена</b>\n\nНапишите правки или нажмите ✅ Утвердить"
        await _send_cover_photo(m, cover_url, caption, state, reply_markup=_image_review_kb())
    else:
        await _send(m, "⚠️ Не удалось сгенерировать. Нажмите ✅ чтобы продолжить.", state, reply_markup=_image_review_kb())


# ── Image review: approve → build ────────────────────────────────────

@router.callback_query(CoverCallback.filter(F.action == "approve"))
async def h_img_approve(cb: CallbackQuery, state: FSMContext):
    lang = _lang(cb)
    await cb.answer()
    await _build(cb.message, state, lang)


# ── Build & publish ───────────────────────────────────────────────────

async def _build(msg, state, lang):
    data = await state.get_data()
    cid = data.get("chat_id", msg.chat.id)
    await _clean(cid, state, msg.bot)

    bmsg = await msg.answer(vocab.MSG_BUILDING if lang == "ru" else vocab.MSG_BUILDING_EN)

    try:
        editorial = await _api.generate_editorial(
            data.get("parsed_article", {}), data.get("chosen_title", "Article"),
        )
        result = await _api.build_and_publish(
            title=data.get("chosen_title", editorial.get("title", "")),
            subtitle=editorial.get("subtitle", ""),
            article_body=editorial.get("article_body", ""),
            short_intro=data.get("short_intro", ""),
            cover_image_url=data.get("cover_url", ""),
            links={**editorial.get("links", {}), "arxiv_url": data.get("source_url", "")},
            figures=data.get("parsed_article", {}).get("figures", []),
            source_url=data.get("source_url", ""),
        )

        pages = result.get("pages", {})
        ru_url = pages.get("ru_html_url", "")
        en_url = pages.get("en_html_url", "")
        teaser_ru = result.get("messages", {}).get("ru_telegram_text", "")
        teaser_en = result.get("messages", {}).get("en_telegram_text", "")

        await _del(bmsg)

        title = data.get("chosen_title", "")
        ru_text = _fmt_final(title, teaser_ru, ru_url)
        en_text = _fmt_final(title, teaser_en, en_url)

        # Cache for lang toggle (survives state.clear)
        _final_cache[cid] = {"ru": ru_text, "en": en_text}

        # Show RU by default, button to switch to EN
        display = ru_text if ru_text.strip() else en_text
        show_next = "en" if ru_text.strip() else "ru"
        await msg.answer(display, reply_markup=_lang_toggle_kb(show_next), disable_web_page_preview=False)

    except Exception as e:
        logger.exception("Build failed")
        await _del(bmsg)
        await msg.answer((vocab.MSG_ERROR if lang == "ru" else vocab.MSG_ERROR_EN).format(error=str(e)))

    await state.clear()


# ── Lang toggle callback ─────────────────────────────────────────────

@router.callback_query(LangCallback.filter())
async def h_lang_toggle(cb: CallbackQuery, callback_data: LangCallback, state: FSMContext):
    """Toggle between RU and EN final message."""
    await cb.answer()
    cid = cb.message.chat.id
    cached = _final_cache.get(cid, {})

    if not cached:
        return

    show = callback_data.show  # "ru" or "en"
    text = cached.get(show, "") or cached.get("ru", "") or cached.get("en", "")
    # Next toggle goes to the other language
    next_show = "ru" if show == "en" else "en"

    try:
        await cb.message.edit_text(text, reply_markup=_lang_toggle_kb(next_show), disable_web_page_preview=False)
    except Exception:
        pass
