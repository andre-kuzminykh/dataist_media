"""
Article pipeline schemas.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001-SC008
"""

from pydantic import BaseModel


class FigureSchema(BaseModel):
    url: str
    filename: str
    caption: str = ""
    figure_id: str = ""
    figure_label: str = ""
    source_base: str = ""


class ParsedArticleSchema(BaseModel):
    abstract: str
    article: str
    figures: list[FigureSchema] = []
    source_url: str
    html_url: str


class EditorialArticleSchema(BaseModel):
    title: str
    subtitle: str = ""
    short_intro: str
    article_body: str
    sections: list[dict] = []
    links: dict = {
        "arxiv_url": "",
        "github_url": "",
        "huggingface_url": "",
    }
    locale: str = "ru"


class CoverAssetSchema(BaseModel):
    prompt: str
    image_url: str = ""
    public_url: str = ""


class HtmlPageArtifactSchema(BaseModel):
    html: str
    slug: str
    filename: str
    locale: str
    metadata: dict = {}


class PublishedPageSchema(BaseModel):
    public_url: str
    asset_urls: list[str] = []
    published_at: str


class TelegramMessageSchema(BaseModel):
    chat_id: str
    text: str
    parse_mode: str = "HTML"


class PipelineRequestSchema(BaseModel):
    source_url: str
    target_languages: list[str] = ["ru", "en"]
    style_profile_id: str = "cinematic_orange_violet_v1"
    html_template_profile_id: str = "dataist_article_v1"
    reference_image_url: str = ""
    prompt_profile_id: str = "default_ai_editorial_v1"


class StepStatusSchema(BaseModel):
    name: str
    status: str = "pending"
    error: str = ""


class DiagnosticsSchema(BaseModel):
    warnings: list[str] = []
    steps: list[StepStatusSchema] = []


class PipelineResponseSchema(BaseModel):
    status: str
    source: dict
    assets: dict = {}
    pages: dict = {}
    messages: dict = {}
    diagnostics: DiagnosticsSchema
