"""ReviewCode — calls backend and routes to answer.

## Traceability
Feature: F001, F002
Scenarios: SC001-SC008
"""

import logging

from aiogram.fsm.context import FSMContext

from bot.service.api.pipeline_api import PipelineAPI

logger = logging.getLogger(__name__)


class ReviewCode:
    """Orchestrate the pipeline call and choose the appropriate answer."""

    def __init__(self) -> None:
        self.pipeline_api = PipelineAPI()

    async def run(self, trigger_data: dict, state: FSMContext) -> dict:
        """Execute the pipeline and return a routing dict for the answer layer.

        Returns a dict with keys ``answer_name`` and ``data``.
        """
        url = trigger_data.get("url")

        if url is None:
            return {
                "answer_name": "review_error",
                "data": {"error": trigger_data.get("error", "invalid_url")},
            }

        try:
            result = await self.pipeline_api.process_arxiv(url)
            return {
                "answer_name": "review_success",
                "data": result,
            }
        except Exception as exc:
            logger.exception("Pipeline call failed for %s", url)
            return {
                "answer_name": "review_error",
                "data": {"error": str(exc)},
            }
