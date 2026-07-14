from fastapi import APIRouter, Depends

from app.api.dependencies import require_internal_authentication
from app.schemas.coverage import CoverageEvaluationRequest, CoverageEvaluationResponse
from app.services.coverage import evaluate_coverage

router = APIRouter(dependencies=[Depends(require_internal_authentication)])


@router.post("/coverage/evaluate", response_model=CoverageEvaluationResponse)
async def evaluate_requirement_coverage(
    payload: CoverageEvaluationRequest,
) -> CoverageEvaluationResponse:
    return evaluate_coverage(payload)
