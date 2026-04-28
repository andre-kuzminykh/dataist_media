"""
ArxivParserService — fetches and parses arXiv HTML articles.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Scenarios: SC001, SC003, SC004

## Business Rules
BR002: Fetch HTML, process as text
BR003: Extract abstract, full text, images, captions
BR005: Continue without figures if none found
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from service.core.exceptions import ParseError

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; DataistBot/1.0; +https://dataist.media)"
)


class ArxivParserService:
    """Fetches arXiv HTML pages and extracts structured article content."""

    # ------------------------------------------------------------------
    # HTTP layer
    # ------------------------------------------------------------------

    @staticmethod
    async def fetch_html(html_url: str) -> str:
        """Fetch the raw HTML of an arXiv article page.

        Raises
        ------
        ParseError
            On any HTTP or network error.
        """
        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
            ) as client:
                response = await client.get(
                    html_url,
                    headers={"User-Agent": _USER_AGENT},
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as exc:
            raise ParseError(
                code="PARSE_001",
                message=(
                    f"HTTP {exc.response.status_code} when fetching "
                    f"{html_url}: {exc.response.reason_phrase}"
                ),
                stage="fetch_html",
                retriable=exc.response.status_code >= 500,
            ) from exc
        except httpx.RequestError as exc:
            raise ParseError(
                code="PARSE_002",
                message=f"Network error fetching {html_url}: {exc}",
                stage="fetch_html",
                retriable=True,
            ) from exc

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_image_url(src: str, source_base: str) -> str:
        """Resolve a potentially relative image *src* to an absolute URL.

        Handles two arXiv HTML formats:
        1. src is just relative path:  "imgs/x.png" + base "/html/2602.11103v1"
           → "https://arxiv.org/html/2602.11103v1/imgs/x.png"
        2. src already starts with paper_id: "2604.22748v1/x1.png"
           → "https://arxiv.org/html/2604.22748v1/x1.png" (no doubling)
        """
        if src.startswith(("http://", "https://")):
            return src

        # Extract paper_id from source_base (e.g. "/html/2604.22748v1" → "2604.22748v1")
        parts = source_base.strip("/").split("/")
        paper_id = parts[-1] if parts else ""

        # If src already starts with paper_id, don't double it
        if paper_id and (src.startswith(paper_id + "/") or src == paper_id):
            return f"https://arxiv.org/html/{src}"

        # Normal case: urljoin with trailing slash to preserve paper_id
        base_path = source_base if source_base.endswith("/") else source_base + "/"
        base = f"https://arxiv.org{base_path}"
        return urljoin(base, src)

    @staticmethod
    def _extract_figures(
        soup: BeautifulSoup,
        source_base: str,
    ) -> list[dict]:
        """Extract figures from ``<figure>`` elements.

        Each returned dict contains: url, filename, caption, figure_id,
        figure_label, source_base.
        """
        figures: list[dict] = []

        for fig in soup.find_all("figure"):
            img = fig.find("img")
            if img is None:
                continue

            src = img.get("src", "")
            if not src:
                continue

            url = ArxivParserService._resolve_image_url(src, source_base)
            filename = src.rsplit("/", 1)[-1] if "/" in src else src

            # Caption — prefer <figcaption>, fall back to title/alt
            figcaption = fig.find("figcaption")
            caption = ""
            if figcaption:
                caption = figcaption.get_text(separator=" ", strip=True)
            elif img.get("title"):
                caption = img["title"]
            elif img.get("alt"):
                caption = img["alt"]

            figure_id = fig.get("id", "")
            # Label text such as "Figure 1:" often lives in a <span>
            label_tag = fig.find(
                "span", class_=lambda c: c and "ltx_tag" in c
            )
            figure_label = (
                label_tag.get_text(strip=True) if label_tag else ""
            )

            figures.append(
                {
                    "url": url,
                    "filename": filename,
                    "caption": caption,
                    "figure_id": figure_id,
                    "figure_label": figure_label,
                    "source_base": source_base,
                }
            )

        return figures

    # ------------------------------------------------------------------
    # Main extraction
    # ------------------------------------------------------------------

    @classmethod
    def parse_article(cls, html: str, source_base: str) -> dict:
        """Parse raw *html* into a structured article dict.

        Parameters
        ----------
        html:
            Raw HTML string of the arXiv article page.
        source_base:
            The path component of the arXiv HTML URL
            (e.g. ``/html/2301.12345v1``), used to resolve relative image
            URLs.

        Returns
        -------
        dict
            Keys: ``abstract``, ``article``, ``figures``.
        """
        soup = BeautifulSoup(html, "lxml")

        # --- Abstract -------------------------------------------------------
        abstract = ""
        # Strategy 1: classic arXiv abs page
        bq = soup.find("blockquote", class_="abstract")
        if bq:
            abstract = bq.get_text(separator=" ", strip=True)
            # Strip leading "Abstract:" label if present
            if abstract.lower().startswith("abstract:"):
                abstract = abstract[len("abstract:"):].strip()
            elif abstract.lower().startswith("abstract"):
                abstract = abstract[len("abstract"):].strip()
        else:
            # Strategy 2: ar5iv / LaTeXML markup
            div = soup.find("div", class_="ltx_abstract")
            if div:
                abstract = div.get_text(separator=" ", strip=True)
                if abstract.lower().startswith("abstract"):
                    abstract = abstract[len("abstract"):].strip()
            else:
                # Strategy 3: look for a <section> whose heading says
                # "Abstract"
                for section in soup.find_all("section"):
                    heading = section.find(["h1", "h2", "h3", "h4"])
                    if heading and "abstract" in heading.get_text().lower():
                        abstract = section.get_text(
                            separator=" ", strip=True
                        )
                        # Remove the heading text itself from the result
                        heading_text = heading.get_text(strip=True)
                        if abstract.startswith(heading_text):
                            abstract = abstract[len(heading_text):].strip()
                        break

        # --- Full text ------------------------------------------------------
        article_text = ""
        article_el = soup.find("article")
        if article_el:
            article_text = article_el.get_text(separator="\n", strip=True)
        else:
            page_content = soup.find("div", class_="ltx_page_content")
            if page_content:
                article_text = page_content.get_text(
                    separator="\n", strip=True
                )
            else:
                body = soup.find("body")
                if body:
                    article_text = body.get_text(separator="\n", strip=True)

        # --- Figures (BR005: gracefully continue if none) -------------------
        figures = cls._extract_figures(soup, source_base)
        if not figures:
            logger.info(
                "No figures found in article at %s — continuing without.",
                source_base,
            )

        return {
            "abstract": abstract,
            "article": article_text,
            "figures": figures,
        }

    # ------------------------------------------------------------------
    # Full async pipeline
    # ------------------------------------------------------------------

    async def parse(self, html_url: str) -> dict:
        """Fetch and parse an arXiv HTML page end-to-end.

        Returns a dict compatible with
        :class:`~service.schema.pipeline.article_schema.ParsedArticleSchema`.

        Missing elements are handled gracefully (NFR-1): an empty string
        is used for absent abstract or article text, and an empty list
        for absent figures.
        """
        html = await self.fetch_html(html_url)

        # Derive source_base from the URL path for image resolution
        from urllib.parse import urlparse

        parsed = urlparse(html_url)
        source_base = parsed.path  # e.g. /html/2301.12345v1

        result = self.parse_article(html, source_base)

        return {
            "abstract": result.get("abstract", ""),
            "article": result.get("article", ""),
            "figures": result.get("figures", []),
            "source_url": html_url,
            "html_url": html_url,
        }
