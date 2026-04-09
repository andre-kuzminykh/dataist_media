"""
Step-by-step pipeline API endpoints for interactive Telegram bot flow.

Provides granular endpoints so the bot can present an interactive flow:
1. Parse article
2. Generate 10 titles
3. User picks / regenerates titles
4. Generate editorial with chosen title
5. Generate cover description
6. User edits cover description
7. Generate cover image
8. Build & publish HTML pages

## Traceability
Feature: F001, F002 -- Interactive step-by-step pipeline
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from service.core.config import config
from service.core.exceptions import (
    AppException,
    GenerationError,
    ParseError,
    PublishError,
    ValidationError,
)
from service.schema.pipeline.article_schema import (
    BuildPublishRequestSchema,
    BuildPublishResponseSchema,
    CoverDescriptionRequestSchema,
    CoverDescriptionResponseSchema,
    CoverEditRequestSchema,
    CoverGenerateRequestSchema,
    CoverGenerateResponseSchema,
    EditorialRequestSchema,
    EditorialResponseSchema,
    ParseRequestSchema,
    ParseResponseSchema,
    TitlesRegenerateRequestSchema,
    TitlesRequestSchema,
    TitlesResponseSchema,
)
from service.service.pipeline.arxiv_parser_service import ArxivParserService
from service.service.pipeline.content_generator_service import ContentGeneratorService
from service.service.pipeline.html_builder_service import HtmlBuilderService
from service.service.pipeline.publisher_service import PublisherService
from service.service.pipeline.telegram_delivery_service import TelegramDeliveryService
from service.service.pipeline.url_resolver_service import URLResolverService
from service.service.pipeline.visual_generator_service import VisualGeneratorService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipeline-steps"])

# --- Service instances (module-level singletons) ---
_url_resolver = URLResolverService()
_arxiv_parser = ArxivParserService()
_content_generator = ContentGeneratorService()
_visual_generator = VisualGeneratorService()
_html_builder = HtmlBuilderService()
_publisher = PublisherService()
_telegram_delivery = TelegramDeliveryService()


# ------------------------------------------------------------------
# Step 1: Parse arXiv URL
# ------------------------------------------------------------------


@router.post(
    "/parse",
    response_model=ParseResponseSchema,
    summary="Parse an arXiv article URL",
    description="Validates the arXiv URL, fetches the HTML page, and extracts structured article content.",
)
async def parse_article(request: ParseRequestSchema) -> dict:
    """Parse arXiv URL and return structured article data."""
    logger.info("Step [parse]: source_url=%s", request.source_url)

    try:
        resolved = _url_resolver.resolve(request.source_url)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    html_url = resolved["html_url"]

    try:
        parsed_article = await _arxiv_parser.parse(html_url)
    except ParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    parsed_article["source_url"] = request.source_url
    parsed_article["html_url"] = html_url

    # Extract short_intro from abstract (first meaningful paragraph)
    short_intro = ""
    abstract = parsed_article.get("abstract", "")
    if abstract:
        for para in abstract.split("\n\n"):
            stripped = para.strip()
            if stripped:
                short_intro = stripped
                break

    return {
        "status": "ok",
        "source": {
            "arxiv_abs_url": resolved["source_url"],
            "arxiv_html_url": html_url,
        },
        "parsed_article": parsed_article,
        "short_intro": short_intro,
    }


# ------------------------------------------------------------------
# Step 2: Generate titles
# ------------------------------------------------------------------


@router.post(
    "/generate-titles",
    response_model=TitlesResponseSchema,
    summary="Generate title options",
    description="Generate multiple title suggestions for the article.",
)
async def generate_titles(request: TitlesRequestSchema) -> dict:
    """Generate 10 title options from article intro and abstract."""
    logger.info("Step [generate-titles]: profile=%s", request.prompt_profile_id)

    try:
        titles = await _content_generator.generate_titles(
            short_intro=request.short_intro,
            abstract=request.abstract,
            prompt_profile_id=request.prompt_profile_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"titles": titles}


# ------------------------------------------------------------------
# Step 3: Regenerate titles from custom title
# ------------------------------------------------------------------


@router.post(
    "/regenerate-titles",
    response_model=TitlesResponseSchema,
    summary="Regenerate titles from a custom title",
    description="Generate new title options inspired by the user's custom title.",
)
async def regenerate_titles(request: TitlesRegenerateRequestSchema) -> dict:
    """Regenerate titles based on a user-provided custom title."""
    logger.info("Step [regenerate-titles]: custom_title=%s", request.custom_title)

    try:
        titles = await _content_generator.regenerate_titles(
            custom_title=request.custom_title,
            short_intro=request.short_intro,
            abstract=request.abstract,
            prompt_profile_id=request.prompt_profile_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"titles": titles}


# ------------------------------------------------------------------
# Step 4: Generate editorial with chosen title
# ------------------------------------------------------------------


@router.post(
    "/generate-editorial",
    response_model=EditorialResponseSchema,
    summary="Generate editorial article",
    description="Generate the full editorial content using a chosen title.",
)
async def generate_editorial(request: EditorialRequestSchema) -> dict:
    """Generate editorial article body, subtitle, links using chosen title."""
    logger.info("Step [generate-editorial]: chosen_title=%s", request.chosen_title)

    try:
        editorial = await _content_generator.generate_editorial(
            parsed_article=request.parsed_article,
            prompt_profile_id=request.prompt_profile_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Override the generated title with the user's chosen title
    editorial["title"] = request.chosen_title

    # Regenerate subtitle to match the chosen title
    try:
        subtitle = await _content_generator.generate_subtitle(
            title=request.chosen_title,
            short_intro=editorial.get("short_intro", ""),
            prompt_profile_id=request.prompt_profile_id,
        )
        editorial["subtitle"] = subtitle
    except GenerationError:
        logger.warning("Subtitle regeneration failed, keeping generated subtitle")

    return {
        "title": editorial["title"],
        "subtitle": editorial.get("subtitle", ""),
        "short_intro": editorial.get("short_intro", ""),
        "article_body": editorial.get("article_body", ""),
        "links": editorial.get("links", {}),
    }


# ------------------------------------------------------------------
# Step 5: Generate cover description
# ------------------------------------------------------------------


@router.post(
    "/generate-cover-description",
    response_model=CoverDescriptionResponseSchema,
    summary="Generate cover image description",
    description="Generate a text description for the cover image based on article summary and style.",
)
async def generate_cover_description(request: CoverDescriptionRequestSchema) -> dict:
    """Generate a short visual cover description (2-3 sentences)."""
    logger.info("Step [generate-cover-description]")

    try:
        description = await _content_generator.generate_cover_description(
            article_summary=request.article_summary,
            prompt_profile_id=request.prompt_profile_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"description": description}


# ------------------------------------------------------------------
# Step 6: Edit cover description
# ------------------------------------------------------------------


@router.post(
    "/edit-cover-description",
    response_model=CoverDescriptionResponseSchema,
    summary="Edit cover description with user feedback",
    description="Adjust the cover image description based on user feedback using LLM.",
)
async def edit_cover_description(request: CoverEditRequestSchema) -> dict:
    """Edit the cover description based on user instructions."""
    logger.info("Step [edit-cover-description]")

    try:
        new_description = await _content_generator.edit_cover_description(
            current_description=request.current_description,
            user_feedback=request.user_feedback,
            prompt_profile_id=request.prompt_profile_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"description": new_description}


# ------------------------------------------------------------------
# Step 7: Generate cover image
# ------------------------------------------------------------------


@router.post(
    "/generate-cover",
    response_model=CoverGenerateResponseSchema,
    summary="Generate cover image",
    description="Generate the cover image from a description and save it.",
)
async def generate_cover(request: CoverGenerateRequestSchema) -> dict:
    """Generate cover image from short description, save locally, return URLs."""
    logger.info("Step [generate-cover]: slug=%s", request.slug)

    try:
        # Build full DALL-E prompt from short description + style
        full_prompt = await _visual_generator.generate_cover_prompt(
            article_summary=request.description,
            style_profile_id=request.style_profile_id,
            prompt_profile_id="default_ai_editorial_v1",
        )
        image_data = await _visual_generator.generate_cover_image(
            full_prompt, style_profile_id=request.style_profile_id
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if image_data is None:
        raise HTTPException(
            status_code=502,
            detail="Cover image generation failed (no image data returned)",
        )

    try:
        relative_path = await _visual_generator.save_cover_locally(
            image_data, request.slug
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    public_url = f"{config.ASSET_PUBLIC_BASE_URL}/{relative_path}"

    return {
        "cover_url": relative_path,
        "public_url": public_url,
    }


# ------------------------------------------------------------------
# Step 8: Build HTML pages & publish
# ------------------------------------------------------------------


@router.post(
    "/build-and-publish",
    response_model=BuildPublishResponseSchema,
    summary="Build HTML pages and publish",
    description="Build branded HTML pages for all target languages, publish them, and generate Telegram messages.",
)
async def build_and_publish(request: BuildPublishRequestSchema) -> dict:
    """Build HTML pages, publish, and prepare Telegram messages."""
    logger.info("Step [build-and-publish]: title=%s", request.title)

    slug = _html_builder._generate_slug(request.title)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    public_base = config.ASSET_PUBLIC_BASE_URL

    pages: dict = {}
    messages: dict = {}
    warnings: list[str] = []
    steps: list[dict] = []

    article_html = _html_builder._build_article_html_from_sections(
        request.article_body, request.figures
    )

    # --- RU HTML ---
    ru_page_url = ""
    if "ru" in request.target_languages:
        try:
            ru_artifact = _html_builder.build_html_page(
                title=request.title,
                subtitle=request.subtitle,
                date=date_str,
                cover_image_url=request.cover_image_url,
                article_html=article_html,
                links=request.links,
                figures=request.figures,
                locale="ru",
                slug=slug,
                og_description=request.short_intro[:200],
                public_base_url=public_base,
            )
            steps.append({"name": "build_html_ru", "status": "ok"})

            ru_published = await _publisher.publish_html(
                html=ru_artifact["html"],
                slug=slug,
                filename=ru_artifact["filename"],
            )
            ru_page_url = ru_published["public_url"]
            pages["ru_html_url"] = ru_page_url
            steps.append({"name": "publish_html_ru", "status": "ok"})
        except Exception as exc:
            steps.append(
                {"name": "build_publish_html_ru", "status": "failed", "error": str(exc)}
            )
            warnings.append(f"RU HTML build/publish failed: {exc}")

    # --- EN HTML ---
    en_page_url = ""
    if "en" in request.target_languages:
        try:
            en_body = await _content_generator.translate_article(
                request.article_body, request.prompt_profile_id
            )
            en_article_html = _html_builder._build_article_html_from_sections(en_body, request.figures)

            en_artifact = _html_builder.build_html_page(
                title=request.title,
                subtitle=request.subtitle,
                date=date_str,
                cover_image_url=request.cover_image_url,
                article_html=en_article_html,
                links=request.links,
                figures=request.figures,
                locale="en",
                slug=slug,
                og_description=request.short_intro[:200],
                public_base_url=public_base,
            )
            steps.append({"name": "build_html_en", "status": "ok"})

            en_published = await _publisher.publish_html(
                html=en_artifact["html"],
                slug=slug,
                filename=en_artifact["filename"],
            )
            en_page_url = en_published["public_url"]
            pages["en_html_url"] = en_page_url
            steps.append({"name": "publish_html_en", "status": "ok"})
        except Exception as exc:
            steps.append(
                {"name": "build_publish_html_en", "status": "failed", "error": str(exc)}
            )
            warnings.append(f"EN HTML build/publish failed: {exc}")

    # --- Teasers ---
    teaser_ru = ""
    teaser_en = ""
    try:
        teaser_ru = await _content_generator.generate_teaser(
            request.title, request.short_intro, "ru", request.prompt_profile_id
        )
    except GenerationError:
        warnings.append("RU teaser generation failed")

    try:
        teaser_en = await _content_generator.generate_teaser(
            request.title, request.short_intro, "en", request.prompt_profile_id
        )
    except GenerationError:
        warnings.append("EN teaser generation failed")

    # --- Telegram messages ---
    try:
        ru_text, en_text = _telegram_delivery._format_telegram_message(
            title=request.title,
            ru_url=ru_page_url,
            en_url=en_page_url,
            teaser_ru=teaser_ru,
            teaser_en=teaser_en,
            cover_url=request.cover_image_url,
        )
        messages["ru_telegram_text"] = ru_text
        messages["en_telegram_text"] = en_text
        steps.append({"name": "build_telegram_messages", "status": "ok"})
    except Exception as exc:
        steps.append(
            {"name": "build_telegram_messages", "status": "failed", "error": str(exc)}
        )
        warnings.append(f"Telegram message building failed: {exc}")

    # --- Deliver to Telegram ---
    if config.TELEGRAM_CHAT_ID and messages.get("ru_telegram_text"):
        try:
            await _telegram_delivery.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=messages["ru_telegram_text"],
                parse_mode="HTML",
            )
            steps.append({"name": "deliver_telegram", "status": "ok"})
        except Exception as exc:
            steps.append(
                {"name": "deliver_telegram", "status": "failed", "error": str(exc)}
            )
            warnings.append(f"Telegram delivery failed: {exc}")

    status = "success"
    if warnings:
        status = "completed_with_warnings"

    return {
        "status": status,
        "pages": pages,
        "messages": messages,
        "diagnostics": {"warnings": warnings, "steps": steps},
    }
