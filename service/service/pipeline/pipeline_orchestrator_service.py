"""
PipelineOrchestratorService — orchestrates the full arXiv → HTML → Telegram pipeline.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Feature: F003 — Configuration Management
Scenarios: SC001-SC010

## State Machine
received → validated → html_resolved → html_fetched → article_parsed → figures_parsed
→ article_summarized → editorial_generated → title_generated → cover_generated
→ cover_uploaded → html_ru_built → html_ru_published → teaser_generated
→ html_en_built → html_en_published → telegram_messages_built → delivered

## Dependencies
- URLResolverService
- ArxivParserService
- ContentGeneratorService
- VisualGeneratorService
- HtmlBuilderService
- PublisherService
- TelegramDeliveryService
"""

import logging
from datetime import datetime, timezone

from service.core.config import config
from service.core.exceptions import (
    AppException,
    ValidationError,
    ParseError,
    GenerationError,
    PublishError,
    DeliveryError,
)
from service.service.pipeline.url_resolver_service import URLResolverService
from service.service.pipeline.arxiv_parser_service import ArxivParserService
from service.service.pipeline.content_generator_service import ContentGeneratorService
from service.service.pipeline.visual_generator_service import VisualGeneratorService
from service.service.pipeline.html_builder_service import HtmlBuilderService
from service.service.pipeline.publisher_service import PublisherService
from service.service.pipeline.telegram_delivery_service import TelegramDeliveryService

logger = logging.getLogger(__name__)


class PipelineOrchestratorService:
    """Orchestrates the full content production pipeline."""

    def __init__(self):
        self.url_resolver = URLResolverService()
        self.arxiv_parser = ArxivParserService()
        self.content_generator = ContentGeneratorService()
        self.visual_generator = VisualGeneratorService()
        self.html_builder = HtmlBuilderService()
        self.publisher = PublisherService()
        self.telegram_delivery = TelegramDeliveryService()

    async def run(
        self,
        source_url: str,
        target_languages: list[str] | None = None,
        prompt_profile_id: str = "default_ai_editorial_v1",
        style_profile_id: str = "cinematic_orange_violet_v1",
        html_template_profile_id: str = "dataist_article_v1",
        reference_image_url: str = "",
    ) -> dict:
        if target_languages is None:
            target_languages = ["ru", "en"]

        steps: list[dict] = []
        warnings: list[str] = []
        result = {
            "status": "success",
            "source": {},
            "assets": {},
            "pages": {},
            "messages": {},
            "diagnostics": {"warnings": warnings, "steps": steps},
        }

        # --- Step 1: Validate & resolve URL ---
        try:
            resolved = self.url_resolver.resolve(source_url)
            result["source"] = {
                "arxiv_abs_url": resolved["source_url"],
                "arxiv_html_url": resolved["html_url"],
            }
            steps.append({"name": "validate_url", "status": "ok"})
        except ValidationError as exc:
            steps.append({"name": "validate_url", "status": "failed", "error": str(exc)})
            result["status"] = "validation_failed"
            return result

        html_url = resolved["html_url"]

        # --- Step 2: Fetch & parse article ---
        parsed_article = None
        try:
            parsed_article = await self.arxiv_parser.parse(html_url)
            parsed_article["source_url"] = source_url
            parsed_article["html_url"] = html_url
            steps.append({"name": "parse_article", "status": "ok"})
        except ParseError as exc:
            steps.append({"name": "parse_article", "status": "failed", "error": str(exc)})
            result["status"] = "html_fetch_failed"
            return result

        if not parsed_article.get("article"):
            steps.append({"name": "parse_article_text", "status": "failed", "error": "no article text"})
            result["status"] = "parse_partial"
            warnings.append("No article text extracted")
            return result

        figures = parsed_article.get("figures", [])
        if not figures:
            warnings.append("No figures extracted from article")
            steps.append({"name": "parse_figures", "status": "partial", "error": "no figures found"})
        else:
            steps.append({"name": "parse_figures", "status": "ok"})

        result["assets"]["figure_images"] = [
            {"url": f.get("url", ""), "caption": f.get("caption", "")} for f in figures
        ]

        # --- Step 3: Generate editorial content ---
        editorial = None
        try:
            editorial = await self.content_generator.generate_editorial(
                parsed_article, prompt_profile_id
            )
            steps.append({"name": "generate_editorial", "status": "ok"})
        except GenerationError as exc:
            steps.append({"name": "generate_editorial", "status": "failed", "error": str(exc)})
            result["status"] = "failed_publish"
            return result

        # --- Step 4: Generate title ---
        try:
            title = await self.content_generator.generate_title(
                editorial.get("short_intro", ""), prompt_profile_id
            )
            editorial["title"] = title
            steps.append({"name": "generate_title", "status": "ok"})
        except GenerationError as exc:
            steps.append({"name": "generate_title", "status": "failed", "error": str(exc)})
            warnings.append("Title generation failed, using fallback")
            editorial.setdefault("title", "Обзор статьи")

        # Generate subtitle
        try:
            subtitle = await self.content_generator.generate_subtitle(
                editorial["title"], editorial.get("short_intro", ""), prompt_profile_id
            )
            editorial["subtitle"] = subtitle
            steps.append({"name": "generate_subtitle", "status": "ok"})
        except GenerationError:
            editorial.setdefault("subtitle", "")
            warnings.append("Subtitle generation failed")

        # Extract links
        try:
            links = await self.content_generator.extract_links(
                parsed_article["article"], prompt_profile_id
            )
            editorial["links"] = links
            editorial["links"]["arxiv_url"] = source_url
            steps.append({"name": "extract_links", "status": "ok"})
        except GenerationError:
            editorial.setdefault("links", {"arxiv_url": source_url})
            warnings.append("Link extraction failed")

        slug = self.html_builder._generate_slug(editorial["title"])
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # --- Step 5: Generate cover ---
        cover_url = ""
        try:
            cover_result = await self.visual_generator.generate_and_save(
                article_summary=editorial.get("short_intro", ""),
                slug=slug,
                style_profile_id=style_profile_id,
                prompt_profile_id=prompt_profile_id,
            )
            cover_url = cover_result.get("public_url", "")
            if cover_url:
                steps.append({"name": "generate_cover", "status": "ok"})
            else:
                steps.append({"name": "generate_cover", "status": "partial", "error": "no image generated"})
                warnings.append("Cover generation returned empty result, using fallback")
        except Exception as exc:
            steps.append({"name": "generate_cover", "status": "failed", "error": str(exc)})
            warnings.append(f"Cover generation failed: {exc}")

        result["assets"]["cover_image_url"] = cover_url
        public_base = config.ASSET_PUBLIC_BASE_URL

        # --- Step 6: Build & publish RU HTML ---
        ru_page_url = ""
        if "ru" in target_languages:
            try:
                article_html = self.html_builder._build_article_html_from_sections(
                    editorial.get("article_body", "")
                )
                ru_artifact = self.html_builder.build_html_page(
                    title=editorial["title"],
                    subtitle=editorial.get("subtitle", ""),
                    date=date_str,
                    cover_image_url=cover_url,
                    article_html=article_html,
                    links=editorial.get("links", {}),
                    figures=figures,
                    locale="ru",
                    slug=slug,
                    og_description=editorial.get("short_intro", "")[:200],
                    public_base_url=public_base,
                )
                steps.append({"name": "build_html_ru", "status": "ok"})

                ru_published = await self.publisher.publish_html(
                    html=ru_artifact["html"],
                    slug=slug,
                    filename=ru_artifact["filename"],
                )
                ru_page_url = ru_published["public_url"]
                result["pages"]["ru_html_url"] = ru_page_url
                steps.append({"name": "publish_html_ru", "status": "ok"})
            except (PublishError, Exception) as exc:
                steps.append({"name": "build_publish_html_ru", "status": "failed", "error": str(exc)})
                warnings.append(f"RU HTML build/publish failed: {exc}")
                result["status"] = "degraded_publish"

        # --- Step 7: Generate teasers ---
        teaser_ru = ""
        teaser_en = ""
        try:
            teaser_ru = await self.content_generator.generate_teaser(
                editorial["title"], editorial.get("short_intro", ""), "ru", prompt_profile_id
            )
            steps.append({"name": "generate_teaser_ru", "status": "ok"})
        except GenerationError:
            warnings.append("RU teaser generation failed")

        # --- Step 8: Build & publish EN HTML ---
        en_page_url = ""
        if "en" in target_languages:
            try:
                en_body = await self.content_generator.translate_article(
                    editorial.get("article_body", ""), prompt_profile_id
                )
                en_article_html = self.html_builder._build_article_html_from_sections(en_body)

                en_title = editorial["title"]  # Could translate title too
                en_artifact = self.html_builder.build_html_page(
                    title=en_title,
                    subtitle=editorial.get("subtitle", ""),
                    date=date_str,
                    cover_image_url=cover_url,
                    article_html=en_article_html,
                    links=editorial.get("links", {}),
                    figures=figures,
                    locale="en",
                    slug=slug,
                    og_description=editorial.get("short_intro", "")[:200],
                    public_base_url=public_base,
                )
                steps.append({"name": "build_html_en", "status": "ok"})

                en_published = await self.publisher.publish_html(
                    html=en_artifact["html"],
                    slug=slug,
                    filename=en_artifact["filename"],
                )
                en_page_url = en_published["public_url"]
                result["pages"]["en_html_url"] = en_page_url
                steps.append({"name": "publish_html_en", "status": "ok"})
            except Exception as exc:
                steps.append({"name": "build_publish_html_en", "status": "failed", "error": str(exc)})
                warnings.append(f"EN HTML build/publish failed: {exc}")

        try:
            teaser_en = await self.content_generator.generate_teaser(
                editorial["title"], editorial.get("short_intro", ""), "en", prompt_profile_id
            )
            steps.append({"name": "generate_teaser_en", "status": "ok"})
        except GenerationError:
            warnings.append("EN teaser generation failed")

        # --- Step 9: Build Telegram messages ---
        try:
            ru_text, en_text = self.telegram_delivery._format_telegram_message(
                title=editorial["title"],
                ru_url=ru_page_url,
                en_url=en_page_url,
                teaser_ru=teaser_ru,
                teaser_en=teaser_en,
                cover_url=cover_url,
            )
            result["messages"]["ru_telegram_text"] = ru_text
            result["messages"]["en_telegram_text"] = en_text
            steps.append({"name": "build_telegram_messages", "status": "ok"})
        except Exception as exc:
            steps.append({"name": "build_telegram_messages", "status": "failed", "error": str(exc)})
            warnings.append(f"Telegram message building failed: {exc}")

        # --- Step 10: Deliver to Telegram ---
        if config.TELEGRAM_CHAT_ID and ru_text:
            try:
                await self.telegram_delivery.send_message(
                    chat_id=config.TELEGRAM_CHAT_ID,
                    text=ru_text,
                    parse_mode="HTML",
                )
                steps.append({"name": "deliver_telegram", "status": "ok"})
            except DeliveryError as exc:
                steps.append({"name": "deliver_telegram", "status": "failed", "error": str(exc)})
                warnings.append(f"Telegram delivery failed: {exc}")

        if result["status"] == "success" and warnings:
            result["status"] = "completed_with_warnings"

        steps.append({"name": "pipeline_complete", "status": "ok"})
        return result
