"""
Test SC005 — Full happy-path tests for content generation services.

Feature: F002 — Editorial Content & HTML Generation
Scenario: SC005 — Successful end-to-end content generation

Verifies HtmlBuilderService markdown-to-HTML conversion, slug generation,
PublisherService file persistence, and TelegramDeliveryService message
formatting.  All external services (OpenAI, Telegram API, filesystem
config) are mocked.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from service.service.pipeline.html_builder_service import HtmlBuilderService
from service.service.pipeline.publisher_service import PublisherService
from service.service.pipeline.telegram_delivery_service import TelegramDeliveryService


# ---------------------------------------------------------------------------
# HtmlBuilderService._build_article_html_from_sections
# ---------------------------------------------------------------------------

class TestBuildArticleHtmlFromSections:
    """Tests for converting markdown-style headings to HTML sections."""

    def test_converts_markdown_headings_to_html(self) -> None:
        """
        Given article body with ## headings
        When _build_article_html_from_sections is called
        Then it returns HTML with <section>, <h2>, and <p> tags.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        body = (
            "## Introduction\n\n"
            "Deep learning is powerful.\n\n"
            "## Method\n\n"
            "We use attention."
        )
        result = builder._build_article_html_from_sections(body)

        assert "<h2>Introduction</h2>" in result
        assert "<h2>Method</h2>" in result
        assert "<section>" in result
        assert "<p>" in result

    def test_returns_html_as_is_if_starts_with_tag(self) -> None:
        """
        Given article body that already starts with an HTML tag
        When _build_article_html_from_sections is called
        Then it returns the content unchanged.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        html_body = "<section><h2>Already HTML</h2><p>Content.</p></section>"
        result = builder._build_article_html_from_sections(html_body)

        assert result == html_body

    def test_empty_body_returns_empty_string(self) -> None:
        """
        Given an empty article body
        When _build_article_html_from_sections is called
        Then it returns an empty string.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        assert builder._build_article_html_from_sections("") == ""
        assert builder._build_article_html_from_sections("   ") == ""

    def test_no_headings_wraps_in_paragraphs(self) -> None:
        """
        Given article body with no ## headings
        When _build_article_html_from_sections is called
        Then each paragraph is wrapped in <p> tags.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        body = "First paragraph.\n\nSecond paragraph."
        result = builder._build_article_html_from_sections(body)

        assert "<p>First paragraph.</p>" in result
        assert "<p>Second paragraph.</p>" in result

    def test_preamble_before_first_heading(self) -> None:
        """
        Given article body with text before the first ## heading
        When _build_article_html_from_sections is called
        Then the preamble text is wrapped in its own section.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        body = "Some preamble text.\n\n## First Section\n\nSection content."
        result = builder._build_article_html_from_sections(body)

        assert "<p>Some preamble text.</p>" in result
        assert "<h2>First Section</h2>" in result


# ---------------------------------------------------------------------------
# HtmlBuilderService._generate_slug
# ---------------------------------------------------------------------------

class TestGenerateSlug:
    """Tests for slug generation from titles."""

    def test_generates_valid_slug(self) -> None:
        """
        Given a title string
        When _generate_slug is called
        Then it returns a lowercase hyphen-separated slug.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        slug = builder._generate_slug("Hello World Paper Title")
        assert slug == "hello-world-paper-title"

    def test_slug_max_length(self) -> None:
        """
        Given a very long title
        When _generate_slug is called
        Then the slug is truncated to max 80 characters.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        long_title = "a " * 100  # 200 chars
        slug = builder._generate_slug(long_title)
        assert len(slug) <= 80

    def test_slug_handles_special_characters(self) -> None:
        """
        Given a title with special characters
        When _generate_slug is called
        Then special characters are removed or transliterated.
        """
        builder = HtmlBuilderService.__new__(HtmlBuilderService)

        slug = builder._generate_slug("Test: A Paper! (2024)")
        assert ":" not in slug
        assert "!" not in slug
        assert "(" not in slug


# ---------------------------------------------------------------------------
# HtmlBuilderService.build_html_page — method signature and structure
# ---------------------------------------------------------------------------

class TestBuildHtmlPageSignature:
    """Tests for the build_html_page method structure."""

    @patch("service.service.pipeline.html_builder_service.config")
    def test_build_html_page_returns_correct_keys(self, mock_config: MagicMock) -> None:
        """
        Given valid inputs and a mocked template
        When build_html_page is called
        Then the result dict has html, slug, filename, locale, metadata keys.
        """
        mock_config.HTML_TEMPLATE_PROFILE_ID = "test_template"

        builder = HtmlBuilderService.__new__(HtmlBuilderService)
        # Mock the jinja environment to return a simple template
        mock_template = MagicMock()
        mock_template.render.return_value = "<html>rendered</html>"

        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        builder._env = mock_env

        result = builder.build_html_page(
            title="Test Title",
            subtitle="Test Subtitle",
            date="2024-01-01",
            cover_image_url="https://example.com/cover.png",
            article_html="<p>Body</p>",
            links={"github_url": ""},
            figures=[],
            locale="ru",
            slug="test-slug",
            og_description="A test article",
            public_base_url="https://dataist.media",
        )

        assert "html" in result
        assert "slug" in result
        assert "filename" in result
        assert "locale" in result
        assert "metadata" in result

    @patch("service.service.pipeline.html_builder_service.config")
    def test_build_html_page_filename_includes_locale(self, mock_config: MagicMock) -> None:
        """
        Given locale='en' and slug='test'
        When build_html_page is called
        Then filename is 'test_en.html'.
        """
        mock_config.HTML_TEMPLATE_PROFILE_ID = "test_template"

        builder = HtmlBuilderService.__new__(HtmlBuilderService)
        mock_template = MagicMock()
        mock_template.render.return_value = "<html></html>"
        mock_env = MagicMock()
        mock_env.get_template.return_value = mock_template
        builder._env = mock_env

        result = builder.build_html_page(
            title="Test",
            subtitle="",
            date="2024-01-01",
            cover_image_url="",
            article_html="<p>Body</p>",
            links={},
            figures=[],
            locale="en",
            slug="test",
            og_description="",
            public_base_url="https://dataist.media",
        )

        assert result["filename"] == "test_en.html"
        assert result["locale"] == "en"


# ---------------------------------------------------------------------------
# PublisherService
# ---------------------------------------------------------------------------

class TestPublisherService:
    """Tests for PublisherService file operations."""

    @pytest.mark.asyncio
    async def test_publish_html_saves_file(self, tmp_path) -> None:
        """
        Given HTML content, a slug, and a filename
        When publish_html is called
        Then the file is saved on disk and the result contains a public_url.
        """
        with patch("service.service.pipeline.publisher_service.config") as mock_config:
            mock_config.ASSET_STORAGE_PATH = str(tmp_path)
            mock_config.ASSET_PUBLIC_BASE_URL = "https://cdn.dataist.media"

            publisher = PublisherService()
            result = await publisher.publish_html(
                html="<html><body>Hello</body></html>",
                slug="test-article",
                filename="test-article_ru.html",
            )

        assert "public_url" in result
        assert "test-article" in result["public_url"]
        assert "published_at" in result

        saved_file = tmp_path / "test-article" / "test-article_ru.html"
        assert saved_file.exists()
        assert saved_file.read_text() == "<html><body>Hello</body></html>"

    @pytest.mark.asyncio
    async def test_publish_html_returns_correct_url(self, tmp_path) -> None:
        """
        Given a configured public base URL
        When publish_html is called
        Then the public_url matches the base URL + slug + filename.
        """
        with patch("service.service.pipeline.publisher_service.config") as mock_config:
            mock_config.ASSET_STORAGE_PATH = str(tmp_path)
            mock_config.ASSET_PUBLIC_BASE_URL = "https://cdn.dataist.media"

            publisher = PublisherService()
            result = await publisher.publish_html(
                html="<html></html>",
                slug="my-slug",
                filename="my-slug_en.html",
            )

        assert result["public_url"] == "https://cdn.dataist.media/my-slug/my-slug_en.html"

    @pytest.mark.asyncio
    async def test_publish_asset_saves_binary(self, tmp_path) -> None:
        """
        Given binary image data
        When publish_asset is called
        Then the binary file is saved and a public URL is returned.
        """
        with patch("service.service.pipeline.publisher_service.config") as mock_config:
            mock_config.ASSET_STORAGE_PATH = str(tmp_path)
            mock_config.ASSET_PUBLIC_BASE_URL = "https://cdn.dataist.media"

            publisher = PublisherService()
            image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # fake PNG
            url = await publisher.publish_asset(
                data=image_data,
                slug="my-article",
                filename="cover.png",
            )

        assert url == "https://cdn.dataist.media/my-article/cover.png"

        saved_file = tmp_path / "my-article" / "cover.png"
        assert saved_file.exists()
        assert saved_file.read_bytes() == image_data

    @pytest.mark.asyncio
    async def test_publish_html_with_assets(self, tmp_path) -> None:
        """
        Given a list of asset relative paths
        When publish_html is called with assets
        Then the asset_urls list is populated.
        """
        with patch("service.service.pipeline.publisher_service.config") as mock_config:
            mock_config.ASSET_STORAGE_PATH = str(tmp_path)
            mock_config.ASSET_PUBLIC_BASE_URL = "https://cdn.dataist.media"

            publisher = PublisherService()
            result = await publisher.publish_html(
                html="<html></html>",
                slug="slug",
                filename="slug_ru.html",
                assets=["slug/cover.png", "slug/fig1.png"],
            )

        assert len(result["asset_urls"]) == 2
        assert "cover.png" in result["asset_urls"][0]


# ---------------------------------------------------------------------------
# TelegramDeliveryService._format_telegram_message
# ---------------------------------------------------------------------------

class TestFormatTelegramMessage:
    """Tests for Telegram message formatting."""

    def test_format_returns_ru_and_en_texts(self) -> None:
        """
        Given title, URLs, teasers, and a cover URL
        When _format_telegram_message is called
        Then it returns a tuple of (ru_text, en_text).
        """
        with patch("service.service.pipeline.telegram_delivery_service.config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "fake-token"

            service = TelegramDeliveryService()
            ru_text, en_text = service._format_telegram_message(
                title="Test Title",
                ru_url="https://dataist.media/test_ru.html",
                en_url="https://dataist.media/test_en.html",
                teaser_ru="Краткое описание статьи.",
                teaser_en="Short article description.",
                cover_url="https://cdn.dataist.media/cover.png",
            )

        assert isinstance(ru_text, str)
        assert isinstance(en_text, str)

    def test_ru_text_contains_title_and_links(self) -> None:
        """
        Given valid input parameters
        When _format_telegram_message is called
        Then the RU text contains the title and reading links.
        """
        with patch("service.service.pipeline.telegram_delivery_service.config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "fake-token"

            service = TelegramDeliveryService()
            ru_text, _ = service._format_telegram_message(
                title="Заголовок",
                ru_url="https://dataist.media/article_ru.html",
                en_url="https://dataist.media/article_en.html",
                teaser_ru="Тизер",
                teaser_en="Teaser",
                cover_url="",
            )

        assert "Заголовок" in ru_text
        assert "Читать статью" in ru_text
        assert "article_ru.html" in ru_text

    def test_en_text_contains_title_and_links(self) -> None:
        """
        Given valid input parameters
        When _format_telegram_message is called
        Then the EN text contains the title and reading links.
        """
        with patch("service.service.pipeline.telegram_delivery_service.config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "fake-token"

            service = TelegramDeliveryService()
            _, en_text = service._format_telegram_message(
                title="Headline",
                ru_url="https://dataist.media/article_ru.html",
                en_url="https://dataist.media/article_en.html",
                teaser_ru="Тизер",
                teaser_en="Teaser",
                cover_url="",
            )

        assert "Headline" in en_text
        assert "Read the article" in en_text
        assert "article_en.html" in en_text

    def test_cover_url_included_when_present(self) -> None:
        """
        Given a non-empty cover_url
        When _format_telegram_message is called
        Then the cover URL is included in both messages.
        """
        with patch("service.service.pipeline.telegram_delivery_service.config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "fake-token"

            service = TelegramDeliveryService()
            ru_text, en_text = service._format_telegram_message(
                title="Title",
                ru_url="https://dataist.media/ru.html",
                en_url="https://dataist.media/en.html",
                teaser_ru="RU",
                teaser_en="EN",
                cover_url="https://cdn.dataist.media/cover.png",
            )

        assert "cover.png" in ru_text
        assert "cover.png" in en_text

    def test_no_cover_url_omits_image_link(self) -> None:
        """
        Given an empty cover_url
        When _format_telegram_message is called
        Then no invisible image link is appended.
        """
        with patch("service.service.pipeline.telegram_delivery_service.config") as mock_config:
            mock_config.TELEGRAM_BOT_TOKEN = "fake-token"

            service = TelegramDeliveryService()
            ru_text, en_text = service._format_telegram_message(
                title="Title",
                ru_url="https://dataist.media/ru.html",
                en_url="https://dataist.media/en.html",
                teaser_ru="RU",
                teaser_en="EN",
                cover_url="",
            )

        # U+200D zero-width joiner used for invisible link
        assert "\u200d" not in ru_text
        assert "\u200d" not in en_text
