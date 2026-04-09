"""
URLResolverService — validates and transforms arXiv URLs.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Scenarios: SC001, SC002

## Business Rules
BR001: Accept arXiv /abs/ URL, transform to /html/...v1
BR004: Validate arXiv domain
"""

import re

from service.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
# Matches arxiv.org /abs/ or /html/ paths with an arXiv paper ID
# Examples:
#   https://arxiv.org/abs/2301.12345
#   https://arxiv.org/abs/2301.12345v2
#   https://arxiv.org/html/2301.12345v1
#   https://ar5iv.labs.arxiv.org/html/2301.12345v1
_ARXIV_URL_RE = re.compile(
    r"^https?://"
    r"(?:(?:www\.)?arxiv\.org|ar5iv\.labs\.arxiv\.org)"
    r"/(?:abs|html)"
    r"/(\d{4}\.\d{4,5})(v\d+)?$"
)

_ARXIV_ABS_RE = re.compile(
    r"^https?://"
    r"(?:(?:www\.)?arxiv\.org|ar5iv\.labs\.arxiv\.org)"
    r"/abs"
    r"/(\d{4}\.\d{4,5})(v\d+)?$"
)

_ARXIV_HTML_RE = re.compile(
    r"^https?://"
    r"(?:(?:www\.)?arxiv\.org|ar5iv\.labs\.arxiv\.org)"
    r"/html"
    r"/(\d{4}\.\d{4,5})(v\d+)?$"
)


class URLResolverService:
    """Validates arXiv URLs and resolves them to canonical HTML endpoints."""

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_url(url: str) -> bool:
        """Return *True* if *url* is a recognised arXiv abs or html URL."""
        return bool(_ARXIV_URL_RE.match(url.strip()))

    @staticmethod
    def resolve_html_url(abs_url: str) -> str:
        """Transform an arXiv /abs/ URL into an /html/…v1 URL.

        * If the URL already points to /html/, it is returned with version
          appended when missing.
        * Both ``arxiv.org`` and ``ar5iv.labs.arxiv.org`` domains are
          supported; the result always uses ``arxiv.org``.
        * If a version suffix is already present it is kept as-is;
          otherwise ``v1`` is appended.
        """
        url = abs_url.strip()

        # Try /abs/ first
        match = _ARXIV_ABS_RE.match(url)
        if match:
            paper_id = match.group(1)
            version = match.group(2) or "v1"
            return f"https://arxiv.org/html/{paper_id}{version}"

        # Already an /html/ URL — normalise domain and ensure version
        match = _ARXIV_HTML_RE.match(url)
        if match:
            paper_id = match.group(1)
            version = match.group(2) or "v1"
            return f"https://arxiv.org/html/{paper_id}{version}"

        raise ValidationError(
            code="URL_001",
            message=f"Cannot resolve URL to arXiv HTML: {url}",
            stage="url_resolution",
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def resolve(self, url: str) -> dict:
        """Validate *url* and return a resolution dict.

        Returns
        -------
        dict
            ``{"source_url": <original>, "html_url": <resolved>, "valid": True}``

        Raises
        ------
        ValidationError
            When *url* is not a valid arXiv URL.
        """
        url = url.strip()

        if not self.validate_url(url):
            raise ValidationError(
                code="URL_002",
                message=f"Invalid arXiv URL: {url}",
                stage="url_resolution",
            )

        html_url = self.resolve_html_url(url)

        return {
            "source_url": url,
            "html_url": html_url,
            "valid": True,
        }
