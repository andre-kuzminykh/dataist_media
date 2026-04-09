"""Bot configuration from environment.

## Traceability
Feature: F001, F002, F003
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    BOT_TOKEN: str
    BACKEND_URL: str = "http://localhost:8000"
    ADMIN_CHAT_IDS: str = ""

    @property
    def admin_chat_id_list(self) -> list[int]:
        """Return parsed list of admin chat IDs."""
        if not self.ADMIN_CHAT_IDS:
            return []
        return [int(cid.strip()) for cid in self.ADMIN_CHAT_IDS.split(",") if cid.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


config = Settings()
