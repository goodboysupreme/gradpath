from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_analysis_provider, require_internal_authentication
from app.providers.base import (
    AnalysisProvider,
    AnalysisProviderError,
    AnalysisProviderNotConfigured,
)
from app.schemas.analysis import ReadinessAnalysisRequest, ReadinessAnalysisResponse
from app.services.analysis import AnalysisGroundingError, evaluate_readiness

router = APIRouter()


@router.post(
    "/analyses/evaluate",
    response_model=ReadinessAnalysisResponse,
    dependencies=[Depends(require_internal_authentication)],
)
async def evaluate_resume_against_jd(
    payload: ReadinessAnalysisRequest,
    provider: Annotated[AnalysisProvider, Depends(get_analysis_provider)],
) -> ReadinessAnalysisResponse:
    try:
        return await evaluate_readiness(payload, provider)
    except AnalysisProviderNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI analysis provider is not configured",
        ) from exc
    except AnalysisGroundingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis was not grounded in supplied evidence",
        ) from exc
    except AnalysisProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI analysis provider failed",
        ) from exc
