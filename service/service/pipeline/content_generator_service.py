"""
ContentGeneratorService — generates editorial content using LLM.

## Traceability
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC005, SC006, SC007

## Business Rules
BR006: Generate RU editorial article
BR007: Extract arXiv/GitHub/HuggingFace links
"""

from __future__ import annotations

import json
import logging
import re

from openai import AsyncOpenAI

from service.config.config_loader import ConfigLoader
from service.core.config import config
from service.core.exceptions import GenerationError

logger = logging.getLogger(__name__)


class ContentGeneratorService:
    """Generates editorial articles and metadata via OpenAI LLM calls."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        self._model = config.OPENAI_MODEL
        self._config_loader = ConfigLoader()

    # ------------------------------------------------------------------
    # Low-level LLM call
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat-completion request and return the assistant text.

        Raises
        ------
        GenerationError
            On any OpenAI API error.
        """
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise GenerationError(
                code="GEN_001",
                message=f"LLM call failed: {exc}",
                stage="llm_call",
                retriable=True,
            ) from exc

    # ------------------------------------------------------------------
    # Editorial generation
    # ------------------------------------------------------------------

    async def generate_editorial(
        self,
        parsed_article: dict,
        prompt_profile_id: str,
    ) -> dict:
        """Generate a full editorial article in Russian.

        Parameters
        ----------
        parsed_article:
            Dict with keys ``abstract``, ``article``, ``figures``.
        prompt_profile_id:
            ID of the prompt profile (e.g. ``"default_ai_editorial_v1"``).

        Returns
        -------
        dict
            Keys: ``title``, ``subtitle``, ``short_intro``,
            ``article_body``, ``links``.
        """
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        glossary = profile.get("glossary", {})
        glossary_text = "\n".join(
            f"- {k}: {v}" for k, v in glossary.items()
        )

        # Prepare figures info
        figures_info = ""
        for fig in parsed_article.get("figures", []):
            label = fig.get("figure_label", "")
            caption = fig.get("caption", "")
            figures_info += f"{label}: {caption}\n"

        # --- Generate the main article body ---------------------------------
        editorial_prompt = prompts.get("editorial", "")
        editorial_prompt = editorial_prompt.format(
            glossary=glossary_text,
            abstract=parsed_article.get("abstract", ""),
            article_text=parsed_article.get("article", ""),
            figures_info=figures_info or "(no figures)",
        )
        article_body = await self._call_llm(editorial_prompt, max_tokens=4096)

        # --- Short intro (first meaningful paragraph) -----------------------
        short_intro = ""
        for para in article_body.split("\n\n"):
            stripped = para.strip()
            if stripped and not stripped.startswith("#"):
                short_intro = stripped
                break

        # --- Title & subtitle -----------------------------------------------
        title = await self.generate_title(short_intro, prompt_profile_id)
        subtitle = await self.generate_subtitle(
            title, short_intro, prompt_profile_id
        )

        # --- Links -----------------------------------------------------------
        links = await self.extract_links(
            parsed_article.get("article", ""), prompt_profile_id
        )

        return {
            "title": title,
            "subtitle": subtitle,
            "short_intro": short_intro,
            "article_body": article_body,
            "links": links,
        }

    # ------------------------------------------------------------------
    # Individual generation steps
    # ------------------------------------------------------------------

    async def generate_title(
        self,
        short_intro: str,
        prompt_profile_id: str,
    ) -> str:
        """Generate a catchy Russian title for the article."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        title_prompt = prompts.get("title", "")
        title_prompt = title_prompt.format(short_intro=short_intro)
        return (await self._call_llm(title_prompt, max_tokens=256)).strip()

    async def generate_subtitle(
        self,
        title: str,
        short_intro: str,
        prompt_profile_id: str,
    ) -> str:
        """Generate a one-sentence Russian subtitle."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        subtitle_prompt = prompts.get("subtitle", "")
        subtitle_prompt = subtitle_prompt.format(
            title=title, short_intro=short_intro
        )
        return (await self._call_llm(subtitle_prompt, max_tokens=256)).strip()

    async def extract_links(
        self,
        article_text: str,
        prompt_profile_id: str,
    ) -> dict:
        """Extract GitHub, HuggingFace, and project links from the paper.

        Returns
        -------
        dict
            Keys: ``github_url``, ``huggingface_url``, ``project_url``,
            ``demo_url`` (each a string, possibly empty).
        """
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        link_prompt = prompts.get("link_extraction", "")
        link_prompt = link_prompt.format(article_text=article_text)

        raw = await self._call_llm(link_prompt, max_tokens=512)

        # Attempt to parse as JSON; fall back to empty dict on failure
        try:
            links = json.loads(raw.strip())
            if not isinstance(links, dict):
                links = {}
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse link extraction response as JSON")
            links = {}

        return {
            "github_url": links.get("github_url", ""),
            "huggingface_url": links.get("huggingface_url", ""),
            "project_url": links.get("project_url", ""),
            "demo_url": links.get("demo_url", ""),
        }

    async def translate_article(
        self,
        article_body: str,
        prompt_profile_id: str,
    ) -> str:
        """Translate a Russian article body into English."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        translation_prompt = prompts.get("translation", "")
        translation_prompt = translation_prompt.format(
            article_body=article_body
        )
        return await self._call_llm(translation_prompt, max_tokens=4096)

    async def generate_teaser(
        self,
        title: str,
        short_intro: str,
        language: str,
        prompt_profile_id: str,
    ) -> str:
        """Generate a Telegram teaser in the given *language*."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        teaser_prompt = prompts.get("teaser", "")
        teaser_prompt = teaser_prompt.format(
            title=title,
            short_intro=short_intro,
            language=language,
        )
        return (await self._call_llm(teaser_prompt, max_tokens=512)).strip()

    # ------------------------------------------------------------------
    # Step-by-step pipeline helpers
    # ------------------------------------------------------------------

    async def generate_titles(
        self,
        short_intro: str,
        abstract: str,
        prompt_profile_id: str,
        count: int = 10,
    ) -> list[str]:
        """Generate multiple title options. Returns list of title strings."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        prompt = prompts.get("titles_generation", "")
        prompt = prompt.format(short_intro=short_intro, abstract=abstract)
        raw = await self._call_llm(prompt, max_tokens=1024)
        # Parse numbered lines: "1. Title\n2. Title\n..."
        titles = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', line).strip()
                if cleaned:
                    titles.append(cleaned)
        return titles[:count]

    async def regenerate_titles(
        self,
        custom_title: str,
        short_intro: str,
        abstract: str,
        prompt_profile_id: str,
        count: int = 10,
    ) -> list[str]:
        """Generate new titles inspired by user's custom title."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        prompt = prompts.get("titles_regeneration", "")
        prompt = prompt.format(
            custom_title=custom_title,
            short_intro=short_intro,
            abstract=abstract,
        )
        raw = await self._call_llm(prompt, max_tokens=1024)
        titles = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                cleaned = re.sub(r'^\d+[\.\)\-]\s*', '', line).strip()
                if cleaned:
                    titles.append(cleaned)
        return titles[:count]

    async def generate_cover_description(
        self,
        article_summary: str,
        prompt_profile_id: str,
    ) -> str:
        """Generate a short visual cover description (2-3 sentences)."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        prompt = prompts.get("cover_description", "")
        prompt = prompt.format(article_summary=article_summary)
        return (await self._call_llm(prompt, max_tokens=256)).strip()

    async def edit_cover_description(
        self,
        current_description: str,
        user_feedback: str,
        prompt_profile_id: str,
    ) -> str:
        """Edit cover description based on user feedback using LLM."""
        profile = self._config_loader.load_prompt_profile(prompt_profile_id)
        prompts = profile.get("prompts", {})
        prompt = prompts.get("cover_description_edit", "")
        prompt = prompt.format(
            current_description=current_description,
            user_feedback=user_feedback,
        )
        return (await self._call_llm(prompt, max_tokens=1024)).strip()
