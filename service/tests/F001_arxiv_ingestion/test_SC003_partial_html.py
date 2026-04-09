"""
Test SC003 — Partial HTML parsing (graceful degradation).

Feature: F001 — arXiv Article Ingestion & Parsing
Scenario: SC003 — arXiv page has missing structural elements

Verifies that ArxivParserService.parse_article handles missing
<figure>, <article>, and abstract elements gracefully without raising
exceptions, returning empty defaults where appropriate.
"""

from __future__ import annotations

import pytest

from service.service.pipeline.arxiv_parser_service import ArxivParserService


_SOURCE_BASE = "/html/2301.12345v1"


# ---------------------------------------------------------------------------
# No figures
# ---------------------------------------------------------------------------

class TestParseArticleNoFigures:
    """HTML without <figure> elements should yield an empty figures list."""

    def test_returns_empty_figures_list(self, sample_html_without_figures: str) -> None:
        """
        Given valid HTML with <article> and abstract but no <figure> tags
        When parse_article is called
        Then the result contains an empty figures list and no exception is raised.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_figures, _SOURCE_BASE,
        )

        assert result["figures"] == []

    def test_abstract_still_extracted(self, sample_html_without_figures: str) -> None:
        """
        Given HTML without figures but with an abstract
        When parse_article is called
        Then the abstract is still correctly extracted.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_figures, _SOURCE_BASE,
        )

        assert "convergence rates" in result["abstract"]

    def test_article_text_still_extracted(self, sample_html_without_figures: str) -> None:
        """
        Given HTML without figures but with article text
        When parse_article is called
        Then the article text is still extracted.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_figures, _SOURCE_BASE,
        )

        assert len(result["article"]) > 0


# ---------------------------------------------------------------------------
# No <article> tag — fallback to <body>
# ---------------------------------------------------------------------------

class TestParseArticleNoArticleTag:
    """HTML without <article> should fall back to <body> text."""

    def test_falls_back_to_body_text(self, sample_html_without_article_tag: str) -> None:
        """
        Given HTML that has no <article> tag
        When parse_article is called
        Then article text is extracted from <body> content.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_article_tag, _SOURCE_BASE,
        )

        assert "no article tag" in result["article"].lower()

    def test_no_exception_raised(self, sample_html_without_article_tag: str) -> None:
        """
        Given HTML without <article> tag
        When parse_article is called
        Then no exception is raised (graceful degradation).
        """
        # Should not raise
        result = ArxivParserService.parse_article(
            sample_html_without_article_tag, _SOURCE_BASE,
        )
        assert isinstance(result, dict)

    def test_result_has_required_keys(self, sample_html_without_article_tag: str) -> None:
        """
        Given HTML without <article> tag
        When parse_article is called
        Then the result still has abstract, article, and figures keys.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_article_tag, _SOURCE_BASE,
        )
        assert "abstract" in result
        assert "article" in result
        assert "figures" in result


# ---------------------------------------------------------------------------
# No abstract
# ---------------------------------------------------------------------------

class TestParseArticleNoAbstract:
    """HTML without any abstract element should return an empty abstract."""

    def test_returns_empty_abstract(self, sample_html_without_abstract: str) -> None:
        """
        Given HTML with <article> but no abstract div/blockquote/section
        When parse_article is called
        Then the abstract key is an empty string.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_abstract, _SOURCE_BASE,
        )

        assert result["abstract"] == ""

    def test_article_text_still_present(self, sample_html_without_abstract: str) -> None:
        """
        Given HTML without abstract
        When parse_article is called
        Then the article body text is still extracted.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_abstract, _SOURCE_BASE,
        )

        assert "skip the abstract" in result["article"].lower()

    def test_no_exception_raised(self, sample_html_without_abstract: str) -> None:
        """
        Given HTML without abstract
        When parse_article is called
        Then no exception is raised.
        """
        result = ArxivParserService.parse_article(
            sample_html_without_abstract, _SOURCE_BASE,
        )
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Completely minimal HTML
# ---------------------------------------------------------------------------

class TestParseArticleMinimalHtml:
    """Edge case: near-empty HTML should not crash."""

    def test_bare_html(self) -> None:
        """
        Given a minimal HTML document with almost no content
        When parse_article is called
        Then it returns a valid dict with empty/default values.
        """
        html = "<html><head></head><body></body></html>"
        result = ArxivParserService.parse_article(html, _SOURCE_BASE)

        assert result["abstract"] == ""
        assert result["figures"] == []
        # article may be empty or very short
        assert isinstance(result["article"], str)
