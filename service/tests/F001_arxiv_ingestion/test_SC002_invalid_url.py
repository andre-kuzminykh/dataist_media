"""
Test SC002 — Invalid arXiv URL handling.

Feature: F001 — arXiv Article Ingestion & Parsing
Scenario: SC002 — User submits an invalid or non-arXiv URL

Verifies that URLResolverService rejects non-arXiv URLs, empty strings,
partial URLs, and other malformed inputs by returning False from
validate_url and raising ValidationError from resolve / resolve_html_url.
"""

from __future__ import annotations

import pytest

from service.core.exceptions import ValidationError
from service.service.pipeline.url_resolver_service import URLResolverService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def resolver() -> URLResolverService:
    """Fresh URLResolverService instance."""
    return URLResolverService()


# ---------------------------------------------------------------------------
# validate_url — negative cases
# ---------------------------------------------------------------------------

class TestValidateUrlNegative:
    """Tests that validate_url returns False for unrecognised URLs."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://google.com",
            "https://arxiv.org/pdf/2301.12345",
            "https://arxiv.org/abs/",
            "https://arxiv.org",
            "ftp://arxiv.org/abs/2301.12345",
            "arxiv.org/abs/2301.12345",
            "https://example.com/abs/2301.12345",
            "https://arxiv.org/abs/not-a-paper",
            "https://arxiv.org/abs/12345",
            "",
            "   ",
            "not-a-url",
        ],
        ids=[
            "google-domain",
            "pdf-path",
            "abs-missing-id",
            "bare-domain",
            "ftp-scheme",
            "no-scheme",
            "wrong-domain-correct-path",
            "non-numeric-id",
            "short-id-no-dot",
            "empty-string",
            "whitespace-only",
            "plain-text",
        ],
    )
    def test_validate_url_returns_false(self, url: str) -> None:
        """
        Given a non-arXiv or malformed URL
        When validate_url is called
        Then it returns False.
        """
        assert URLResolverService.validate_url(url) is False


# ---------------------------------------------------------------------------
# resolve — raises ValidationError
# ---------------------------------------------------------------------------

class TestResolveRaisesValidationError:
    """Tests that resolve() raises ValidationError for invalid inputs."""

    def test_resolve_raises_for_non_arxiv_url(self, resolver: URLResolverService) -> None:
        """
        Given a non-arXiv URL
        When resolve() is called
        Then ValidationError is raised with code URL_002.
        """
        with pytest.raises(ValidationError) as exc_info:
            resolver.resolve("https://google.com/abs/2301.12345")

        assert exc_info.value.code == "URL_002"
        assert exc_info.value.stage == "url_resolution"

    def test_resolve_raises_for_empty_string(self, resolver: URLResolverService) -> None:
        """
        Given an empty string
        When resolve() is called
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError) as exc_info:
            resolver.resolve("")

        assert exc_info.value.code == "URL_002"

    def test_resolve_raises_for_whitespace(self, resolver: URLResolverService) -> None:
        """
        Given a whitespace-only string
        When resolve() is called
        Then ValidationError is raised.
        """
        with pytest.raises(ValidationError):
            resolver.resolve("   ")

    @pytest.mark.parametrize(
        "url",
        [
            "https://arxiv.org/pdf/2301.12345",
            "https://arxiv.org/abs/",
            "https://example.com",
            "not a url at all",
        ],
        ids=["pdf-path", "missing-id", "wrong-domain", "gibberish"],
    )
    def test_resolve_raises_for_various_invalid(
        self, resolver: URLResolverService, url: str,
    ) -> None:
        """
        Given various invalid URL formats
        When resolve() is called
        Then ValidationError is raised for each one.
        """
        with pytest.raises(ValidationError):
            resolver.resolve(url)


# ---------------------------------------------------------------------------
# resolve_html_url — raises ValidationError
# ---------------------------------------------------------------------------

class TestResolveHtmlUrlRaisesValidationError:
    """Tests that resolve_html_url raises for completely invalid URLs."""

    def test_raises_for_unrecognised_url(self) -> None:
        """
        Given a URL that is neither /abs/ nor /html/
        When resolve_html_url is called
        Then ValidationError is raised with code URL_001.
        """
        with pytest.raises(ValidationError) as exc_info:
            URLResolverService.resolve_html_url("https://google.com/paper")

        assert exc_info.value.code == "URL_001"
        assert exc_info.value.stage == "url_resolution"

    def test_validation_error_attributes(self) -> None:
        """
        Given an invalid URL
        When ValidationError is raised
        Then it contains code, message, stage, and retriable attributes.
        """
        with pytest.raises(ValidationError) as exc_info:
            URLResolverService.resolve_html_url("https://bad-url.com")

        err = exc_info.value
        assert hasattr(err, "code")
        assert hasattr(err, "message")
        assert hasattr(err, "stage")
        assert hasattr(err, "retriable")
        assert err.retriable is False
