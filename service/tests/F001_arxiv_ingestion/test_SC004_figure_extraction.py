"""
Test SC004 — Figure extraction from arXiv HTML.

Feature: F001 — arXiv Article Ingestion & Parsing
Scenario: SC004 — Extracting figures, captions, and image URLs

Verifies that ArxivParserService._extract_figures correctly extracts
url, caption, figure_id, and figure_label from <figure> elements, and
that _resolve_image_url handles both relative and absolute URLs.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from service.service.pipeline.arxiv_parser_service import ArxivParserService


_SOURCE_BASE = "/html/2301.12345v1"


# ---------------------------------------------------------------------------
# _extract_figures
# ---------------------------------------------------------------------------

class TestExtractFigures:
    """Tests for ArxivParserService._extract_figures."""

    def test_extracts_all_figures(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with two <figure> elements
        When _extract_figures is called
        Then it returns a list with two figure dicts.
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert len(figures) == 2

    def test_figure_dict_has_required_keys(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with figures
        When _extract_figures is called
        Then each figure dict has url, caption, figure_id, figure_label keys.
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        required_keys = {"url", "filename", "caption", "figure_id", "figure_label", "source_base"}
        for fig in figures:
            assert required_keys.issubset(fig.keys()), (
                f"Missing keys: {required_keys - set(fig.keys())}"
            )

    def test_figure_id_extracted(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with <figure id="fig1">
        When _extract_figures is called
        Then figure_id equals "fig1".
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert figures[0]["figure_id"] == "fig1"
        assert figures[1]["figure_id"] == "fig2"

    def test_figure_label_extracted(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with <span class="ltx_tag ltx_tag_figure">Figure 1:</span>
        When _extract_figures is called
        Then figure_label equals "Figure 1:".
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert figures[0]["figure_label"] == "Figure 1:"
        assert figures[1]["figure_label"] == "Figure 2:"

    def test_caption_extracted_from_figcaption(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with <figcaption> containing caption text
        When _extract_figures is called
        Then the caption text is extracted.
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert "Loss landscape" in figures[0]["caption"]
        assert "Convergence" in figures[1]["caption"]

    def test_relative_url_resolved(self, sample_html_with_figures: str) -> None:
        """
        Given a figure with a relative src path
        When _extract_figures is called
        Then the url is resolved to an absolute URL under arxiv.org.
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        # First figure has a relative URL
        assert figures[0]["url"].startswith("https://arxiv.org/")
        assert "figure1.png" in figures[0]["url"]

    def test_absolute_url_preserved(self, sample_html_with_figures: str) -> None:
        """
        Given a figure with an absolute src URL
        When _extract_figures is called
        Then the url is preserved as-is.
        """
        soup = BeautifulSoup(sample_html_with_figures, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        # Second figure has an absolute URL
        assert figures[1]["url"] == "https://arxiv.org/html/2301.12345v1/extracted/figure2.png"

    def test_no_figures_returns_empty_list(self) -> None:
        """
        Given HTML without any <figure> tags
        When _extract_figures is called
        Then it returns an empty list.
        """
        html = "<html><body><p>No figures here.</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert figures == []

    def test_figure_without_img_skipped(self) -> None:
        """
        Given a <figure> that has no <img> child
        When _extract_figures is called
        Then that figure is skipped.
        """
        html = """<html><body>
        <figure id="fig1">
            <figcaption>Caption without image</figcaption>
        </figure>
        </body></html>"""
        soup = BeautifulSoup(html, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert figures == []

    def test_figure_with_empty_src_skipped(self) -> None:
        """
        Given a <figure> whose <img> has an empty src attribute
        When _extract_figures is called
        Then that figure is skipped.
        """
        html = """<html><body>
        <figure id="fig1">
            <img src="" alt="Empty source" />
        </figure>
        </body></html>"""
        soup = BeautifulSoup(html, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert figures == []

    def test_caption_falls_back_to_alt(self) -> None:
        """
        Given a <figure> with no <figcaption> but an alt attribute on <img>
        When _extract_figures is called
        Then the caption is taken from the alt attribute.
        """
        html = """<html><body>
        <figure id="fig1">
            <img src="/img/test.png" alt="Alt text caption" />
        </figure>
        </body></html>"""
        soup = BeautifulSoup(html, "lxml")
        figures = ArxivParserService._extract_figures(soup, _SOURCE_BASE)

        assert len(figures) == 1
        assert figures[0]["caption"] == "Alt text caption"


# ---------------------------------------------------------------------------
# _resolve_image_url
# ---------------------------------------------------------------------------

class TestResolveImageUrl:
    """Tests for ArxivParserService._resolve_image_url."""

    def test_relative_url_resolved_correctly(self) -> None:
        """
        Given a relative image path like "extracted/img.png"
        When _resolve_image_url is called with source_base
        Then it returns an absolute URL under arxiv.org.
        """
        result = ArxivParserService._resolve_image_url(
            "extracted/img.png", _SOURCE_BASE,
        )

        assert result.startswith("https://arxiv.org/")
        assert "img.png" in result

    def test_absolute_http_url_unchanged(self) -> None:
        """
        Given an absolute http:// URL
        When _resolve_image_url is called
        Then it is returned unchanged.
        """
        absolute = "http://example.com/images/fig.png"
        result = ArxivParserService._resolve_image_url(absolute, _SOURCE_BASE)

        assert result == absolute

    def test_absolute_https_url_unchanged(self) -> None:
        """
        Given an absolute https:// URL
        When _resolve_image_url is called
        Then it is returned unchanged.
        """
        absolute = "https://arxiv.org/html/2301.12345v1/extracted/fig.png"
        result = ArxivParserService._resolve_image_url(absolute, _SOURCE_BASE)

        assert result == absolute

    @pytest.mark.parametrize(
        "relative_src, expected_substring",
        [
            ("extracted/fig1.png", "fig1.png"),
            ("./images/chart.svg", "chart.svg"),
            ("/html/2301.12345v1/data/table.png", "table.png"),
        ],
        ids=["simple-relative", "dot-relative", "absolute-path"],
    )
    def test_various_relative_paths(self, relative_src: str, expected_substring: str) -> None:
        """
        Given various relative image paths
        When _resolve_image_url is called
        Then the result contains the expected filename.
        """
        result = ArxivParserService._resolve_image_url(relative_src, _SOURCE_BASE)
        assert expected_substring in result
        # All relative results should become absolute URLs
        assert result.startswith("https://")

    def test_figures_have_arxiv_domain(self, sample_html_with_figures: str) -> None:
        """
        Given HTML with figures that have relative URLs
        When parsing the article
        Then all figure URLs are under the arxiv.org domain.
        """
        result = ArxivParserService.parse_article(
            sample_html_with_figures, _SOURCE_BASE,
        )

        for fig in result["figures"]:
            assert "arxiv.org" in fig["url"], (
                f"Expected arxiv.org domain in URL: {fig['url']}"
            )
