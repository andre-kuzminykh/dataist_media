"""
Test SC008 — HTML build logic.

Feature: F002 — Editorial Content & HTML Generation
Scenario: SC008 — HTML builder converts article body and constructs OG meta

Verifies _build_article_html_from_sections with various input types,
_build_og_meta returns correct metadata, and empty body handling.
"""

from __future__ import annotations

import pytest

from service.service.pipeline.html_builder_service import HtmlBuilderService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_builder() -> HtmlBuilderService:
    """Create an HtmlBuilderService without initialising the Jinja env."""
    return HtmlBuilderService.__new__(HtmlBuilderService)


# ---------------------------------------------------------------------------
# _build_article_html_from_sections — various inputs
# ---------------------------------------------------------------------------

class TestBuildArticleHtmlVariousInputs:
    """Tests for _build_article_html_from_sections with edge cases."""

    def test_single_heading_section(self) -> None:
        """
        Given body with one ## heading and one paragraph
        When _build_article_html_from_sections is called
        Then exactly one <section> with <h2> is produced.
        """
        builder = _make_builder()
        body = "## Only Section\n\nSome content here."
        result = builder._build_article_html_from_sections(body)

        assert result.count("<h2>") == 1
        assert "<h2>Only Section</h2>" in result
        assert "<p>Some content here.</p>" in result

    def test_multiple_heading_sections(self) -> None:
        """
        Given body with three ## headings
        When _build_article_html_from_sections is called
        Then three <section> blocks are produced.
        """
        builder = _make_builder()
        body = (
            "## Section A\n\nContent A.\n\n"
            "## Section B\n\nContent B.\n\n"
            "## Section C\n\nContent C."
        )
        result = builder._build_article_html_from_sections(body)

        assert result.count("<h2>") == 3
        assert result.count("<section>") == 3

    def test_plain_text_no_headings(self) -> None:
        """
        Given body with no ## headings, just paragraphs
        When _build_article_html_from_sections is called
        Then each paragraph is wrapped in <p> tags.
        """
        builder = _make_builder()
        body = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        result = builder._build_article_html_from_sections(body)

        assert result.count("<p>") == 3
        assert "<h2>" not in result

    def test_html_content_returned_unchanged(self) -> None:
        """
        Given body starting with <
        When _build_article_html_from_sections is called
        Then the body is returned unchanged (no processing).
        """
        builder = _make_builder()
        html = "<div><p>Already processed HTML</p></div>"
        result = builder._build_article_html_from_sections(html)

        assert result == html

    def test_whitespace_only_returns_empty(self) -> None:
        """
        Given body with only whitespace
        When _build_article_html_from_sections is called
        Then an empty string is returned.
        """
        builder = _make_builder()

        assert builder._build_article_html_from_sections("") == ""
        assert builder._build_article_html_from_sections("   \n  \t  ") == ""

    def test_heading_with_empty_body(self) -> None:
        """
        Given a heading followed by no content
        When _build_article_html_from_sections is called
        Then the section has the heading but empty body.
        """
        builder = _make_builder()
        body = "## Empty Section\n\n"
        result = builder._build_article_html_from_sections(body)

        assert "<h2>Empty Section</h2>" in result

    def test_multiple_paragraphs_under_heading(self) -> None:
        """
        Given a heading followed by multiple paragraphs
        When _build_article_html_from_sections is called
        Then all paragraphs appear within the same section.
        """
        builder = _make_builder()
        body = "## Details\n\nFirst paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = builder._build_article_html_from_sections(body)

        assert "<h2>Details</h2>" in result
        assert result.count("<p>") == 3


# ---------------------------------------------------------------------------
# _build_og_meta
# ---------------------------------------------------------------------------

class TestBuildOgMeta:
    """Tests for OpenGraph metadata construction."""

    def test_returns_correct_keys(self) -> None:
        """
        Given standard inputs
        When _build_og_meta is called
        Then the returned dict has title, description, image, url, locale.
        """
        builder = _make_builder()
        result = builder._build_og_meta(
            title="Test Title",
            description="A description",
            image_url="https://cdn.example.com/cover.png",
            public_url="https://example.com/article",
            locale="ru",
        )

        assert set(result.keys()) == {"title", "description", "image", "url", "locale"}

    def test_ru_locale_maps_to_ru_RU(self) -> None:
        """
        Given locale='ru'
        When _build_og_meta is called
        Then the OG locale is 'ru_RU'.
        """
        builder = _make_builder()
        result = builder._build_og_meta(
            title="T", description="D",
            image_url="", public_url="", locale="ru",
        )

        assert result["locale"] == "ru_RU"

    def test_en_locale_maps_to_en_US(self) -> None:
        """
        Given locale='en'
        When _build_og_meta is called
        Then the OG locale is 'en_US'.
        """
        builder = _make_builder()
        result = builder._build_og_meta(
            title="T", description="D",
            image_url="", public_url="", locale="en",
        )

        assert result["locale"] == "en_US"

    def test_values_passed_through(self) -> None:
        """
        Given specific title, description, image, url values
        When _build_og_meta is called
        Then those values appear unchanged in the result.
        """
        builder = _make_builder()
        result = builder._build_og_meta(
            title="My Article",
            description="About AI breakthroughs",
            image_url="https://cdn.test.com/img.png",
            public_url="https://test.com/my-article/page.html",
            locale="en",
        )

        assert result["title"] == "My Article"
        assert result["description"] == "About AI breakthroughs"
        assert result["image"] == "https://cdn.test.com/img.png"
        assert result["url"] == "https://test.com/my-article/page.html"

    @pytest.mark.parametrize(
        "locale, expected_og_locale",
        [
            ("ru", "ru_RU"),
            ("en", "en_US"),
            ("fr", "en_US"),  # non-ru defaults to en_US
        ],
        ids=["russian", "english", "french-fallback"],
    )
    def test_locale_mapping_parametrized(
        self, locale: str, expected_og_locale: str,
    ) -> None:
        """
        Given various locale values
        When _build_og_meta is called
        Then the OG locale maps correctly.
        """
        builder = _make_builder()
        result = builder._build_og_meta(
            title="T", description="D",
            image_url="", public_url="", locale=locale,
        )

        assert result["locale"] == expected_og_locale


# ---------------------------------------------------------------------------
# Empty article body
# ---------------------------------------------------------------------------

class TestEmptyArticleBody:
    """Tests for empty or whitespace-only article body."""

    def test_empty_string_returns_empty(self) -> None:
        """
        Given an empty string article body
        When _build_article_html_from_sections is called
        Then an empty string is returned.
        """
        builder = _make_builder()
        assert builder._build_article_html_from_sections("") == ""

    def test_none_like_whitespace_returns_empty(self) -> None:
        """
        Given a whitespace-only article body
        When _build_article_html_from_sections is called
        Then an empty string is returned.
        """
        builder = _make_builder()
        assert builder._build_article_html_from_sections("  \n\n  ") == ""
