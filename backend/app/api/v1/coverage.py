from fastapi import APIRouter

from app.schemas.coverage import CoverageEvaluationRequest, CoverageEvaluationResponse
from app.services.coverage import evaluate_coverage

router = APIRouter()


@router.post("/coverage/evaluate", response_model=CoverageEvaluationResponse)
async def evaluate_requirement_coverage(
    payload: CoverageEvaluationRequest,
) -> CoverageEvaluationResponse:
    return evaluate_coverage(payload)
