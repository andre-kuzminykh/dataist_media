"""
HtmlBuilderService — assembles branded HTML pages from template.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005, SC008

## Business Rules
BR008: Create RU/EN HTML pages
FR-13 through FR-20: HTML template requirements
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import jinja2
from slugify import slugify

from service.core.config import config

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "config" / "templates"


class HtmlBuilderService:
    """Assembles branded HTML article pages using Jinja2 templates."""

    def __init__(self) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_html_page(
        self,
        title: str,
        subtitle: str,
        date: str,
        cover_image_url: str,
        article_html: str,
        links: dict,
        figures: list[dict],
        locale: str,
        slug: str,
        og_description: str,
        public_base_url: str,
    ) -> dict:
        """Render a full HTML page from the article template.

        Parameters
        ----------
        title : str
            Article headline.
        subtitle : str
            Secondary headline / deck.
        date : str
            Publication date string.
        cover_image_url : str
            URL to the cover image.
        article_html : str
            Pre-rendered HTML body of the article.  If the content uses
            markdown-style ``##`` headings it will be converted via
            :meth:`_build_article_html_from_sections`.
        links : dict
            External links (arXiv, GitHub, HuggingFace, etc.).
        figures : list[dict]
            Figure metadata dicts (url, caption, etc.).
        locale : str
            Language code (``"ru"`` or ``"en"``).
        slug : str
            URL-safe identifier for the article.
        og_description : str
            OpenGraph description text.
        public_base_url : str
            Base URL used for canonical / OG URLs.

        Returns
        -------
        dict
            ``{"html": ..., "slug": ..., "filename": ..., "locale": ...,
            "metadata": {...}}``
        """
        if not slug:
            slug = self._generate_slug(title)

        filename = f"{slug}_{locale}.html"
        public_url = f"{public_base_url}/{slug}/{filename}"

        # Convert markdown-like sections to HTML if necessary
        processed_html = self._build_article_html_from_sections(article_html)

        og_meta = self._build_og_meta(
            title=title,
            description=og_description,
            image_url=cover_image_url,
            public_url=public_url,
            locale=locale,
        )

        template = self._env.get_template(f"{config.HTML_TEMPLATE_PROFILE_ID}.html")
        rendered = template.render(
            title=title,
            subtitle=subtitle,
            date=date,
            cover_image_url=cover_image_url,
            article_html=processed_html,
            links=links,
            figures=figures,
            locale=locale,
            slug=slug,
            og=og_meta,
            public_base_url=public_base_url,
        )

        metadata = {
            "og": og_meta,
            "locale": locale,
            "public_url": public_url,
        }

        return {
            "html": rendered,
            "slug": slug,
            "filename": filename,
            "locale": locale,
            "metadata": metadata,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_og_meta(
        self,
        title: str,
        description: str,
        image_url: str,
        public_url: str,
        locale: str,
    ) -> dict:
        """Create an OpenGraph metadata dictionary.

        Parameters
        ----------
        title : str
            OG title.
        description : str
            OG description.
        image_url : str
            OG image URL.
        public_url : str
            Canonical page URL.
        locale : str
            Language code.

        Returns
        -------
        dict
            Keys: ``title``, ``description``, ``image``, ``url``, ``locale``.
        """
        og_locale = "ru_RU" if locale == "ru" else "en_US"
        return {
            "title": title,
            "description": description,
            "image": image_url,
            "url": public_url,
            "locale": og_locale,
        }

    def _build_article_html_from_sections(self, article_body: str) -> str:
        """Convert markdown-like content with ``##`` headings into HTML.

        If the body already looks like pure HTML (starts with ``<``) it is
        returned unchanged.  Otherwise the text is split on ``##`` heading
        lines and each section is wrapped in a ``<section>`` with ``<h2>``
        and ``<p>`` tags.

        Parameters
        ----------
        article_body : str
            Raw article text that may contain ``##`` headings.

        Returns
        -------
        str
            HTML-formatted article content.
        """
        stripped = article_body.strip()
        if not stripped:
            return ""

        # Already HTML — return as-is
        if stripped.startswith("<"):
            return stripped

        # No markdown headings — wrap everything in paragraphs
        if "## " not in stripped:
            paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]
            return "\n".join(f"<p>{p}</p>" for p in paragraphs)

        # Split by ## headings
        sections: list[str] = []
        parts = re.split(r"^## (.+)$", stripped, flags=re.MULTILINE)

        # parts[0] is text before the first heading (preamble)
        preamble = parts[0].strip()
        if preamble:
            paragraphs = [p.strip() for p in preamble.split("\n\n") if p.strip()]
            section_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)
            sections.append(f"<section>\n{section_html}\n</section>")

        # Remaining parts alternate: heading, body, heading, body, ...
        for i in range(1, len(parts), 2):
            heading = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
            body_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)
            sections.append(
                f"<section>\n<h2>{heading}</h2>\n{body_html}\n</section>"
            )

        return "\n".join(sections)

    def _generate_slug(self, title: str) -> str:
        """Create a URL-safe slug from the given title.

        Parameters
        ----------
        title : str
            Article title (may be in any language).

        Returns
        -------
        str
            Lowercased, hyphen-separated, URL-safe slug.
        """
        return slugify(title, max_length=80)
