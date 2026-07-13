from typing import Literal

from pydantic import Field

from app.schemas.base import ContractModel
from app.schemas.domain import CareerTrack


class TrackCapability(ContractModel):
    id: CareerTrack
    workflow: Literal["application", "allotment"]
    supports_preferences: bool
    supports_continuous_evaluation: bool


class CapabilitiesResponse(ContractModel):
    tracks: tuple[TrackCapability, ...]
    resume_template_ids: tuple[str, ...]


class ResumeSection(ContractModel):
    key: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=100)
    layout: Literal["inline", "list", "table"]
    columns: tuple[str, ...] = ()
    required: bool = False


class ResumeTemplateDefinition(ContractModel):
    id: str = Field(min_length=3, max_length=100)
    name: str = Field(min_length=3, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    page_size: Literal["A4"]
    max_pages: Literal[1]
    includes_photo: bool
    institutional_layout: bool
    header_fields: tuple[str, ...]
    sections: tuple[ResumeSection, ...]
