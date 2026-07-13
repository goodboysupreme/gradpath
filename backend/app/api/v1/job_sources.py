from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.api.dependencies import (
    require_internal_authentication,
    verify_source_ingestion_authentication,
)
from app.config import Settings, get_settings
from app.schemas.job_sources import (
    PRIVILEGED_SOURCE_IDS,
    JobDescriptionNormalizationRequest,
    JobSourceRegistryResponse,
    NormalizedJobDescriptionResponse,
)
from app.services.job_sources import job_source_registry, normalize_job_description

router = APIRouter()


@router.get("/job-sources", response_model=JobSourceRegistryResponse)
async def read_job_sources() -> JobSourceRegistryResponse:
    return job_source_registry()


@router.post(
    "/job-descriptions/normalize",
    response_model=NormalizedJobDescriptionResponse,
    dependencies=[Depends(require_internal_authentication)],
)
async def normalize_job_description_payload(
    payload: JobDescriptionNormalizationRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    source_ingestion_token: Annotated[
        str | None,
        Header(alias="X-GradPath-Source-Ingestion-Token"),
    ] = None,
) -> NormalizedJobDescriptionResponse:
    response.headers["Cache-Control"] = "no-store"
    if payload.source_id in PRIVILEGED_SOURCE_IDS:
        verify_source_ingestion_authentication(settings, source_ingestion_token)
    return normalize_job_description(payload)
