"""
Test SC001 — Valid arXiv URL parsing.

Feature: F001 — arXiv Article Ingestion & Parsing
Scenario: SC001 — User submits a valid arXiv URL

Verifies that URLResolverService correctly validates recognised arXiv
URLs, transforms /abs/ paths to /html/...v1, preserves existing version
suffixes, and produces the expected resolution dict.
"""

from __future__ import annotations

import pytest

from service.service.pipeline.url_resolver_service import URLResolverService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def resolver() -> URLResolverService:
    """Fresh URLResolverService instance."""
    return URLResolverService()


# ---------------------------------------------------------------------------
# validate_url — positive cases
# ---------------------------------------------------------------------------

class TestValidateUrlPositive:
    """Tests that validate_url returns True for all recognised formats."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://arxiv.org/abs/2301.12345",
            "https://arxiv.org/abs/2301.12345v1",
            "https://arxiv.org/abs/2301.12345v2",
            "https://arxiv.org/html/2301.12345v1",
            "https://arxiv.org/html/2301.12345",
            "https://www.arxiv.org/abs/2301.12345",
            "https://ar5iv.labs.arxiv.org/abs/2301.12345",
            "https://ar5iv.labs.arxiv.org/html/2301.12345v1",
            "http://arxiv.org/abs/2301.12345",
            "https://arxiv.org/abs/2501.99999",
        ],
        ids=[
            "abs-no-version",
            "abs-v1",
            "abs-v2",
            "html-v1",
            "html-no-version",
            "www-prefix",
            "ar5iv-abs",
            "ar5iv-html-v1",
            "http-scheme",
            "five-digit-id",
        ],
    )
    def test_validate_url_returns_true(self, url: str) -> None:
        """
        Given a valid arXiv URL in a recognised format
        When validate_url is called
        Then it returns True.
        """
        assert URLResolverService.validate_url(url) is True

    def test_validate_url_strips_whitespace(self) -> None:
        """
        Given a valid URL wrapped in leading/trailing whitespace
        When validate_url is called
        Then it still returns True.
        """
        assert URLResolverService.validate_url("  https://arxiv.org/abs/2301.12345  ") is True


# ---------------------------------------------------------------------------
# resolve_html_url — transformation logic
# ---------------------------------------------------------------------------

class TestResolveHtmlUrl:
    """Tests that resolve_html_url transforms URLs correctly."""

    def test_abs_to_html_appends_v1(self) -> None:
        """
        Given an /abs/ URL without a version suffix
        When resolve_html_url is called
        Then it returns an /html/ URL with v1 appended.
        """
        result = URLResolverService.resolve_html_url("https://arxiv.org/abs/2301.12345")
        assert result == "https://arxiv.org/html/2301.12345v1"

    def test_abs_to_html_keeps_existing_version(self) -> None:
        """
        Given an /abs/ URL with version v2
        When resolve_html_url is called
        Then it returns an /html/ URL preserving v2.
        """
        result = URLResolverService.resolve_html_url("https://arxiv.org/abs/2301.12345v2")
        assert result == "https://arxiv.org/html/2301.12345v2"

    def test_html_url_passes_through(self) -> None:
        """
        Given an /html/ URL with version
        When resolve_html_url is called
        Then it is returned as-is (normalised to arxiv.org domain).
        """
        result = URLResolverService.resolve_html_url("https://arxiv.org/html/2301.12345v1")
        assert result == "https://arxiv.org/html/2301.12345v1"

    def test_html_url_without_version_appends_v1(self) -> None:
        """
        Given an /html/ URL without a version suffix
        When resolve_html_url is called
        Then v1 is appended.
        """
        result = URLResolverService.resolve_html_url("https://arxiv.org/html/2301.12345")
        assert result == "https://arxiv.org/html/2301.12345v1"

    def test_ar5iv_domain_normalised_to_arxiv(self) -> None:
        """
        Given an ar5iv.labs.arxiv.org URL
        When resolve_html_url is called
        Then the result uses the arxiv.org domain.
        """
        result = URLResolverService.resolve_html_url(
            "https://ar5iv.labs.arxiv.org/abs/2301.12345"
        )
        assert result.startswith("https://arxiv.org/html/")

    @pytest.mark.parametrize(
        "url, expected",
        [
            (
                "https://arxiv.org/abs/2301.12345",
                "https://arxiv.org/html/2301.12345v1",
            ),
            (
                "https://arxiv.org/abs/2301.12345v3",
                "https://arxiv.org/html/2301.12345v3",
            ),
            (
                "https://ar5iv.labs.arxiv.org/html/2301.12345v1",
                "https://arxiv.org/html/2301.12345v1",
            ),
        ],
        ids=["abs-no-ver", "abs-with-ver", "ar5iv-html"],
    )
    def test_resolve_html_url_parametrized(self, url: str, expected: str) -> None:
        """
        Given various valid arXiv URLs
        When resolve_html_url is called
        Then it returns the expected canonical /html/ URL.
        """
        assert URLResolverService.resolve_html_url(url) == expected


# ---------------------------------------------------------------------------
# resolve — full method
# ---------------------------------------------------------------------------

class TestResolve:
    """Tests that the resolve() method returns the expected dict."""

    def test_resolve_returns_correct_dict(self, resolver: URLResolverService) -> None:
        """
        Given a valid arXiv /abs/ URL
        When resolve() is called
        Then it returns a dict with source_url, html_url, and valid=True.
        """
        result = resolver.resolve("https://arxiv.org/abs/2301.12345")

        assert result["source_url"] == "https://arxiv.org/abs/2301.12345"
        assert result["html_url"] == "https://arxiv.org/html/2301.12345v1"
        assert result["valid"] is True

    def test_resolve_with_html_url(self, resolver: URLResolverService) -> None:
        """
        Given a valid arXiv /html/ URL with version
        When resolve() is called
        Then it returns the same URL as html_url.
        """
        result = resolver.resolve("https://arxiv.org/html/2301.12345v1")

        assert result["html_url"] == "https://arxiv.org/html/2301.12345v1"
        assert result["valid"] is True

    def test_resolve_dict_has_three_keys(self, resolver: URLResolverService) -> None:
        """
        Given a valid URL
        When resolve() is called
        Then the result dict has exactly source_url, html_url, valid keys.
        """
        result = resolver.resolve("https://arxiv.org/abs/2301.12345")
        assert set(result.keys()) == {"source_url", "html_url", "valid"}
