"""
Pipeline API — process arXiv article endpoint.

## Traceability
Feature: F001 — arXiv Article Ingestion & Parsing
Feature: F002 — Editorial Content & HTML Generation
Scenarios: SC001, SC002, SC005, SC008
"""

import logging

from fastapi import APIRouter

from service.schema.pipeline.article_schema import (
    PipelineRequestSchema,
    PipelineResponseSchema,
)
from service.service.pipeline.pipeline_orchestrator_service import (
    PipelineOrchestratorService,
)

logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = PipelineOrchestratorService()


@router.post(
    "/process",
    response_model=PipelineResponseSchema,
    summary="Process arXiv article through the full pipeline",
    description=(
        "Accepts an arXiv URL and runs the full content production pipeline: "
        "parse article → generate editorial → generate cover → build HTML → publish → deliver."
    ),
)
async def process_pipeline(request: PipelineRequestSchema) -> dict:
    """
    Run the full arXiv → HTML → Telegram pipeline.

    Given: A valid arXiv URL
    When: Pipeline is executed
    Then: Returns branded HTML pages, cover, Telegram messages
    """
    logger.info("Pipeline request received: %s", request.source_url)

    result = await orchestrator.run(
        source_url=request.source_url,
        target_languages=request.target_languages,
        prompt_profile_id=request.prompt_profile_id,
        style_profile_id=request.style_profile_id,
        html_template_profile_id=request.html_template_profile_id,
        reference_image_url=request.reference_image_url,
    )

    logger.info("Pipeline completed with status: %s", result["status"])
    return result
