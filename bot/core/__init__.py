"""Core package — bot instance, dispatcher, and config."""

from bot.core.config import config
from bot.core.loader import bot, dp

__all__ = ["bot", "dp", "config"]
