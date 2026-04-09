"""
Application settings loaded from environment variables.

Uses pydantic-settings to validate and parse configuration.
All defaults can be overridden via a .env file or exported shell variables.

Feature IDs: F-CORE-CONFIG
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Dataist arXiv Pipeline API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- LLM -----------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.4"
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"

    # --- Telegram delivery ---------------------------------------------------
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # --- Asset storage -------------------------------------------------------
    ASSET_STORAGE_TYPE: str = "local"  # local | s3 | github
    ASSET_STORAGE_PATH: str = "./published"
    ASSET_PUBLIC_BASE_URL: str = "http://localhost:8000/static"

    # --- Profile selectors ---------------------------------------------------
    PROMPT_PROFILE_ID: str = "default_ai_editorial_v1"
    STYLE_PROFILE_ID: str = "cinematic_orange_violet_v1"
    HTML_TEMPLATE_PROFILE_ID: str = "dataist_article_v1"

    # --- Image generation ----------------------------------------------------
    REFERENCE_IMAGE_URL: str = ""

    # --- Server --------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"


config = Settings()
