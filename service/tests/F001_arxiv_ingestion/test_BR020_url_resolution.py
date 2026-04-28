"""
Test BR020 — arXiv URL resolution preserves paper ID.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Scenario: SC017 — Figures from arXiv display correctly
Business rule: BR020 — Relative URLs must resolve with paper ID

## BDD
Given: Image src is relative (e.g. "imgs/x.png" or "x1.png")
When:  _resolve_image_url(src, source_base) is called
Then:  Returns absolute URL with paper ID preserved
"""

import pytest

from service.service.pipeline.arxiv_parser_service import ArxivParserService


class TestResolveImageUrlPaperIdPreserved:
    """BR020: urljoin must keep paper ID in path (trailing / on base)."""

    @pytest.mark.parametrize(
        "src, source_base, expected",
        [
            (
                "imgs/x.png",
                "/html/2602.11103v1",
                "https://arxiv.org/html/2602.11103v1/imgs/x.png",
            ),
            (
                "x1.png",
                "/html/2602.11103v1",
                "https://arxiv.org/html/2602.11103v1/x1.png",
            ),
            (
                "imgs/example.png",
                "/html/2301.12345v2",
                "https://arxiv.org/html/2301.12345v2/imgs/example.png",
            ),
            # Already-absolute URL untouched
            (
                "https://example.com/img.png",
                "/html/2301.12345v1",
                "https://example.com/img.png",
            ),
            (
                "http://other.com/x.png",
                "/html/2301.12345v1",
                "http://other.com/x.png",
            ),
            # src already includes paper_id (don't double it)
            (
                "2604.22748v1/x1.png",
                "/html/2604.22748v1",
                "https://arxiv.org/html/2604.22748v1/x1.png",
            ),
            (
                "2301.12345v2/imgs/example.png",
                "/html/2301.12345v2",
                "https://arxiv.org/html/2301.12345v2/imgs/example.png",
            ),
        ],
        ids=[
            "subdir-imgs",
            "root-relative",
            "diff-paper-subdir",
            "https-passthrough",
            "http-passthrough",
            "src-includes-paper-id-no-double",
            "src-includes-paper-id-with-subdir",
        ],
    )
    def test_url_resolution(self, src, source_base, expected):
        """
        Given: Relative image src and source_base path
        When:  _resolve_image_url is called
        Then:  Paper ID is preserved in the resolved URL
        """
        result = ArxivParserService._resolve_image_url(src, source_base)
        assert result == expected

    def test_source_base_with_trailing_slash_works(self):
        """
        Given: source_base already has trailing slash
        When:  Resolving relative URL
        Then:  No double slash, correct URL
        """
        result = ArxivParserService._resolve_image_url(
            "imgs/x.png", "/html/2602.11103v1/"
        )
        assert result == "https://arxiv.org/html/2602.11103v1/imgs/x.png"
        assert "//imgs" not in result
