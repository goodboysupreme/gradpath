from fastapi import APIRouter, HTTPException, status

from app.schemas.catalog import CapabilitiesResponse, ResumeTemplateDefinition
from app.services.catalog import capabilities, get_resume_template

router = APIRouter()


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def read_capabilities() -> CapabilitiesResponse:
    return capabilities()


@router.get(
    "/resume-templates/{template_id}",
    response_model=ResumeTemplateDefinition,
)
async def read_resume_template(template_id: str) -> ResumeTemplateDefinition:
    try:
        return get_resume_template(template_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume template not found",
        ) from exc
