"""
Global bot test fixtures.

## Traceability
Feature: F001, F002
"""
import os

# Set required env vars before any bot module is imported at collection time.
os.environ.setdefault("BOT_TOKEN", "0000000000:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_message():
    """Mock aiogram Message object."""
    msg = AsyncMock()
    msg.from_user = MagicMock(id=123, username="testuser", language_code="ru")
    msg.text = "Hello"
    msg.answer = AsyncMock()
    msg.chat = MagicMock(id=456)
    return msg


@pytest.fixture
def mock_message_en():
    """Mock aiogram Message for English user."""
    msg = AsyncMock()
    msg.from_user = MagicMock(id=124, username="testuser_en", language_code="en")
    msg.text = "Hello"
    msg.answer = AsyncMock()
    msg.chat = MagicMock(id=457)
    return msg


@pytest.fixture
def mock_state():
    """Mock aiogram FSMContext."""
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.set_data = AsyncMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    return state


@pytest.fixture
def sample_pipeline_result():
    """Sample successful pipeline result from backend."""
    return {
        "status": "success",
        "source": {
            "arxiv_abs_url": "https://arxiv.org/abs/2301.12345",
            "arxiv_html_url": "https://arxiv.org/html/2301.12345v1",
        },
        "assets": {
            "cover_image_url": "http://localhost:8000/static/test/cover.png",
            "figure_images": [],
        },
        "pages": {
            "ru_html_url": "http://localhost:8000/static/test/test_ru.html",
            "en_html_url": "http://localhost:8000/static/test/test_en.html",
        },
        "messages": {
            "ru_telegram_text": "<b>Test Title</b>\n\nTeaser\n\nLink",
            "en_telegram_text": "<b>Test Title</b>\n\nTeaser\n\nLink",
        },
        "diagnostics": {"warnings": [], "steps": []},
    }
