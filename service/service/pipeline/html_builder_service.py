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

        title_main = title
        subtitle_part = subtitle

        filename = f"{slug}_{locale}.html"
        public_url = f"{public_base_url}/{slug}/{filename}"

        # Convert markdown-like sections to HTML if necessary
        processed_html = self._build_article_html_from_sections(article_html, figures)

        # OG image: use cover if HTTPS, otherwise fallback to reference
        og_image = cover_image_url
        if og_image and not og_image.startswith("https://"):
            og_image = "https://raw.githubusercontent.com/andre-kuzminykh/dataist/refs/heads/main/2026-04-03/_ChatGPT%20Image%20Apr%203%2C%202026%2C%2011_25_03%20PM.jpg"

        # OG uses full title (main + subtitle combined)
        full_title = f"{title_main}: {subtitle_part}" if subtitle_part else title_main
        og_meta = self._build_og_meta(
            title=full_title,
            description=og_description,
            image_url=og_image,
            public_url=public_url,
            locale=locale,
        )

        template = self._env.get_template(f"{config.HTML_TEMPLATE_PROFILE_ID}.html")
        rendered = template.render(
            title=title_main,
            subtitle=subtitle_part,
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

    def _build_article_html_from_sections(
        self, article_body: str, figures: list[dict] | None = None
    ) -> str:
        """Convert markdown-like content with ``##`` headings into HTML.

        Processes ``[FIGURE:N]`` and ``[CAPTION:text]`` markers to insert
        figure elements inline where the LLM placed them.
        """
        stripped = article_body.strip()
        if not stripped:
            return ""

        if stripped.startswith("<"):
            return stripped

        figures = figures or []
        logger.info(
            "Build article HTML: figures_count=%d, body_has_figure_marker=%s",
            len(figures),
            "[FIGURE" in stripped.upper(),
        )

        def _process_block(text: str) -> str:
            """Convert a text block into HTML, handling figure markers and markdown bold."""
            lines_out = []
            in_figure = False

            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # [FIGURE:N] marker — case insensitive, with optional whitespace
                fig_match = re.match(r"\[\s*figure\s*:?\s*(\d+)\s*\]", line, re.IGNORECASE)
                if fig_match:
                    # Close previous unclosed figure
                    if in_figure:
                        lines_out.append("</div></figure>")
                        in_figure = False

                    idx = int(fig_match.group(1))
                    if 0 <= idx < len(figures):
                        fig = figures[idx]
                        url = fig.get("url", "")
                        if url:
                            used_figures.add(idx)
                            lines_out.append(
                                f'<figure class="my-10 md:my-14 fade-in max-w-4xl mx-auto w-full">'
                                f'<div class="arxiv-chart flex flex-col items-center">'
                                f'<img src="{url}" alt="" class="w-full object-contain rounded-lg bg-white/50">'
                            )
                            in_figure = True
                    continue

                # [CAPTION:text] marker — case insensitive
                cap_match = re.match(r"\[\s*caption\s*:?\s*(.+)\]", line, re.IGNORECASE)
                if cap_match:
                    caption = cap_match.group(1).strip()
                    lines_out.append(
                        f'<p class="text-sm md:text-base text-gray-800 dark:text-gray-300 mt-5 '
                        f'text-center font-mono max-w-3xl leading-relaxed">{caption}</p>'
                    )
                    if in_figure:
                        lines_out.append("</div></figure>")
                        in_figure = False
                    continue

                # Close unclosed figure before regular content
                if in_figure:
                    lines_out.append("</div></figure>")
                    in_figure = False

                # Convert markdown **bold** to <strong>
                line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                # Convert markdown *italic* to <em>
                line = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', line)

                # List item (- item) → styled card
                list_match = re.match(r'^[-•]\s+(.+)', line)
                if list_match:
                    item = list_match.group(1)
                    # Metric pattern: "Name: 0.507 → 0.585" or "Name — value"
                    metric_match = re.match(r'^(.+?):\s*(.+?)\s*→\s*(.+)$', item)
                    if metric_match:
                        name = metric_match.group(1).strip()
                        old_val = metric_match.group(2).strip()
                        new_val = metric_match.group(3).strip()
                        lines_out.append(
                            f'<div class="tech-card rounded-xl px-5 py-3 mb-2 flex justify-between items-center">'
                            f'<span class="font-mono font-bold text-sm">{name}</span>'
                            f'<span class="font-mono text-sm">'
                            f'<span class="opacity-50">{old_val}</span>'
                            f' → '
                            f'<span class="text-cyber-orange font-bold">{new_val}</span>'
                            f'</span></div>'
                        )
                    else:
                        lines_out.append(
                            f'<div class="tech-card rounded-xl px-5 py-3 mb-2">'
                            f'<span class="text-sm">{item}</span></div>'
                        )
                    continue

                # Regular paragraph
                lines_out.append(f"<p>{line}</p>")

            # Close any trailing unclosed figure
            if in_figure:
                lines_out.append("</div></figure>")

            return "\n".join(lines_out)

        used_figures: set[int] = set()

        if "## " not in stripped:
            return _process_block(stripped)

        sections: list[str] = []
        parts = re.split(r"^## (.+)$", stripped, flags=re.MULTILINE)

        preamble = parts[0].strip()
        if preamble:
            sections.append(f"<section>\n{_process_block(preamble)}\n</section>")

        section_count = 0
        for i in range(1, len(parts), 2):
            heading = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sections.append(
                f"<section>\n<h2>{heading}</h2>\n{_process_block(body)}\n</section>"
            )
            section_count += 1

        # FALLBACK: if LLM didn't place any figures, auto-distribute them
        logger.info("Figures placed by LLM: %d, total available: %d, sections: %d",
                     len(used_figures), len([f for f in figures if f.get("url")]), section_count)
        if not used_figures and figures and section_count > 0:
            available = [(i, f) for i, f in enumerate(figures) if f.get("url")]
            logger.info("Fallback: distributing %d figures across %d sections", len(available), section_count)
            max_figs = min(len(available), 4, max(1, section_count))
            if max_figs > 0 and available:
                # Pick figures evenly: first, middle, etc.
                step = max(1, len(available) // max_figs)
                picked = available[::step][:max_figs]
                # Insert after every section_count // max_figs sections
                section_step = max(1, section_count // max_figs)
                new_sections = []
                fig_idx = 0
                for s_idx, sec in enumerate(sections):
                    new_sections.append(sec)
                    # Insert figure after this section if it's a step boundary
                    if (s_idx + 1) % section_step == 0 and fig_idx < len(picked):
                        idx, fig = picked[fig_idx]
                        caption = f"Иллюстрация {fig_idx + 1}"
                        new_sections.append(
                            f'<figure class="my-10 md:my-14 fade-in max-w-4xl mx-auto w-full">'
                            f'<div class="arxiv-chart flex flex-col items-center">'
                            f'<img src="{fig["url"]}" alt="" class="w-full object-contain rounded-lg bg-white/50">'
                            f'<p class="text-sm md:text-base text-gray-800 dark:text-gray-300 mt-5 '
                            f'text-center font-mono max-w-3xl leading-relaxed">{caption}</p>'
                            f'</div></figure>'
                        )
                        fig_idx += 1
                sections = new_sections

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
