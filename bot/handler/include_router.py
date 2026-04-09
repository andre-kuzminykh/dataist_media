"""Include all routers into the dispatcher.

## Traceability
Feature: F001, F002, F003
"""

from aiogram import Dispatcher

from bot.handler.v1.user.review.router import review_router


def include_routers(dp: Dispatcher) -> None:
    """Register all feature routers with the dispatcher."""
    dp.include_router(review_router)
