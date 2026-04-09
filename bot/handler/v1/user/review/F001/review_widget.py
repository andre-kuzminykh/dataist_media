"""
Widget: arXiv Review Pipeline.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001, SC002, SC005

SC001 — valid arXiv URL -> answer: review_success
SC002 — invalid URL -> answer: review_error
SC005 — full pipeline -> answer: review_success
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.core import vocab
from bot.state.review_state import ReviewStates
from bot.node.review.trigger.review_trigger import ReviewTrigger
from bot.node.review.code.review_code import ReviewCode
from bot.node.review.answer.review_processing_answer import ReviewProcessingAnswer
from bot.node.review.answer.review_success_answer import ReviewSuccessAnswer
from bot.node.review.answer.review_error_answer import ReviewErrorAnswer

logger = logging.getLogger(__name__)

router = Router(name="review_widget")

# ── Answer registry ───────────────────────────────────────────────────
ANSWER_REGISTRY: dict[str, ReviewSuccessAnswer | ReviewErrorAnswer] = {
    "review_success": ReviewSuccessAnswer(),
    "review_error": ReviewErrorAnswer(),
}

# ── Node instances ────────────────────────────────────────────────────
_trigger = ReviewTrigger()
_code = ReviewCode()
_processing_answer = ReviewProcessingAnswer()


def _user_lang(message: Message) -> str:
    """Detect user language from Telegram locale."""
    lang = (message.from_user.language_code or "ru") if message.from_user else "ru"
    return "ru" if lang.startswith("ru") else "en"


async def _run_pipeline(message: Message, state: FSMContext) -> None:
    """Execute the Trigger -> Code -> Answer chain."""
    lang = _user_lang(message)

    # 1. Trigger — extract URL
    trigger_data = await _trigger.run(message, state)

    # 2. Processing answer (optimistic notification)
    if trigger_data.get("url"):
        await state.set_state(ReviewStates.processing)
        await _processing_answer.run(message, user_lang=lang)

    # 3. Code — call backend
    code_result = await _code.run(trigger_data, state)

    # 4. Answer — route to the right answer node
    answer_name = code_result["answer_name"]
    answer_node = ANSWER_REGISTRY.get(answer_name)
    if answer_node:
        await answer_node.run(message, user_lang=lang, data=code_result["data"])
    else:
        logger.error("Unknown answer_name: %s", answer_name)

    # 5. Clear state
    await state.clear()


# ── Handlers ──────────────────────────────────────────────────────────


@router.message(Command(vocab.CMD_START))
async def handle_start(message: Message) -> None:
    """Handle /start command."""
    lang = _user_lang(message)
    text = vocab.MSG_WELCOME if lang == "ru" else vocab.MSG_WELCOME_EN
    await message.answer(text)


@router.message(Command(vocab.CMD_HELP))
async def handle_help(message: Message) -> None:
    """Handle /help command."""
    lang = _user_lang(message)
    text = vocab.MSG_HELP if lang == "ru" else vocab.MSG_HELP_EN
    await message.answer(text)


@router.message(Command(vocab.CMD_REVIEW))
async def handle_review_command(message: Message, state: FSMContext) -> None:
    """Handle /review command.

    If the command contains a URL argument, process immediately.
    Otherwise, ask the user to send a URL and enter the waiting state.
    """
    args = (message.text or "").split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        # URL provided inline — process right away
        await _run_pipeline(message, state)
    else:
        # No URL — ask and wait
        lang = _user_lang(message)
        text = vocab.MSG_SEND_URL if lang == "ru" else vocab.MSG_SEND_URL_EN
        await message.answer(text)
        await state.set_state(ReviewStates.waiting_for_url)


@router.message(ReviewStates.waiting_for_url, F.text)
async def handle_review_url(message: Message, state: FSMContext) -> None:
    """Handle text message while waiting for an arXiv URL."""
    await _run_pipeline(message, state)
