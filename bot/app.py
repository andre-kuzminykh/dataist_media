"""Telegram bot entry point.

## Traceability
Feature: F001, F002, F003
"""

import asyncio
import logging

from bot.core.loader import bot, dp
from bot.handler.include_router import include_routers


async def main() -> None:
    """Configure logging, include routers, and start polling."""
    logging.basicConfig(level=logging.INFO)
    include_routers(dp)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
