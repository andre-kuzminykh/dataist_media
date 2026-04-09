"""
Test SC011 — Interactive title selection in bot.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenario: SC011 — User selects from 10 generated titles or writes custom

## BDD
Given: Article successfully parsed
When:  Bot generates 10 titles and shows them
Then:  User sees numbered buttons (1-10) and "Write your own" button
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.node.review.trigger.review_trigger import ReviewTrigger


@pytest.fixture
def sample_titles():
    """10 sample titles for testing."""
    return [
        "Новый подход к обучению моделей",
        "Революция в архитектуре трансформеров",
        "Масштабирование меняет правила игры",
        "От теории к практике в NLP",
        "Эффективное обучение без данных",
        "Будущее AI-агентов",
        "Мультимодальный прорыв",
        "Дистилляция знаний по-новому",
        "Цепочки рассуждений 2.0",
        "AI понимает контекст лучше",
    ]


class TestTitleCallbackData:
    """Tests for TitleCallback data class."""

    def test_title_pick_callback_packs(self):
        """
        Given: TitleCallback with action=pick, index=3
        When:  Packed to string
        Then:  Contains expected prefix and values
        """
        from bot.callback.review_callback import TitleCallback

        cb = TitleCallback(action="pick", index=3)
        packed = cb.pack()
        assert "ttl" in packed
        assert "pick" in packed

    def test_title_custom_callback_packs(self):
        """
        Given: TitleCallback with action=custom
        When:  Packed to string
        Then:  Contains expected prefix
        """
        from bot.callback.review_callback import TitleCallback

        cb = TitleCallback(action="custom", index=0)
        packed = cb.pack()
        assert "ttl" in packed
        assert "custom" in packed

    def test_title_callback_unpacks(self):
        """
        Given: Packed callback data
        When:  Unpacked
        Then:  Preserves action and index
        """
        from bot.callback.review_callback import TitleCallback

        cb = TitleCallback(action="pick", index=7)
        packed = cb.pack()
        unpacked = TitleCallback.unpack(packed)
        assert unpacked.action == "pick"
        assert unpacked.index == 7


class TestCoverCallbackData:
    """Tests for CoverCallback data class."""

    def test_cover_edit_callback(self):
        """
        Given: CoverCallback with action=edit
        When:  Packed and unpacked
        Then:  Action preserved
        """
        from bot.callback.review_callback import CoverCallback

        cb = CoverCallback(action="edit")
        packed = cb.pack()
        unpacked = CoverCallback.unpack(packed)
        assert unpacked.action == "edit"

    def test_cover_generate_callback(self):
        """
        Given: CoverCallback with action=generate
        When:  Packed and unpacked
        Then:  Action preserved
        """
        from bot.callback.review_callback import CoverCallback

        cb = CoverCallback(action="generate")
        packed = cb.pack()
        unpacked = CoverCallback.unpack(packed)
        assert unpacked.action == "generate"


class TestReviewStates:
    """Tests for the new FSM states."""

    def test_all_states_exist(self):
        """
        Given: ReviewStates class
        When:  Checking state attributes
        Then:  All interactive flow states are defined
        """
        from bot.state.review_state import ReviewStates

        assert hasattr(ReviewStates, "waiting_for_url")
        assert hasattr(ReviewStates, "choosing_title")
        assert hasattr(ReviewStates, "typing_custom_title")
        assert hasattr(ReviewStates, "viewing_cover_description")
        assert hasattr(ReviewStates, "typing_cover_edit")
        assert hasattr(ReviewStates, "generating_image")
        assert hasattr(ReviewStates, "building")


class TestPipelineAPINewMethods:
    """Tests for new PipelineAPI methods."""

    @pytest.mark.asyncio
    async def test_generate_titles_calls_endpoint(self):
        """
        Given: PipelineAPI instance
        When:  generate_titles is called
        Then:  Calls POST /api/v1/pipeline/generate-titles
        """
        from bot.service.api.pipeline_api import PipelineAPI

        api = PipelineAPI(base_url="http://test:8000")

        mock_response = MagicMock()
        mock_response.json.return_value = {"titles": ["Title 1", "Title 2"]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            titles = await api.generate_titles("intro", "abstract")

        assert titles == ["Title 1", "Title 2"]
        mock_client.post.assert_called_once()
        call_url = mock_client.post.call_args[0][0]
        assert "/generate-titles" in call_url

    @pytest.mark.asyncio
    async def test_edit_cover_description_calls_endpoint(self):
        """
        Given: PipelineAPI instance
        When:  edit_cover_description is called
        Then:  Calls POST /api/v1/pipeline/edit-cover-description
        """
        from bot.service.api.pipeline_api import PipelineAPI

        api = PipelineAPI(base_url="http://test:8000")

        mock_response = MagicMock()
        mock_response.json.return_value = {"description": "Updated description"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            desc = await api.edit_cover_description("old desc", "feedback")

        assert desc == "Updated description"
