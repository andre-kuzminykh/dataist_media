"""Review feature router aggregator.

Re-exports the review widget router so it can be included
by the top-level router setup.
"""

from bot.handler.v1.user.review.F001.review_widget import router as review_router

__all__ = ["review_router"]
