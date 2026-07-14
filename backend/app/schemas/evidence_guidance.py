from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.schemas.base import ContractModel
from app.schemas.coverage import (
    CoverageEvaluationRequest,
    CoverageStatus,
    CoverageSummary,
    Identifier,
    RequirementPriority,
)
from app.schemas.domain import CareerTrack, OpportunityKind
from app.schemas.job_sources import (
    CatalogEligibility,
    NormalizedJobDescriptionResponse,
    PostingVerification,
)


class ResumeActionKind(StrEnum):
    SURFACE_EVIDENCE = "surface_evidence"


class PathwayActionKind(StrEnum):
    VERIFY_EVIDENCE = "verify_evidence"
    VERIFY_AND_BUILD_EVIDENCE = "verify_and_build_evidence"
    BUILD_EVIDENCE = "build_evidence"


class ResumeSectionKey(StrEnum):
    PROJECTS = "projects"
    INTERNSHIPS = "internships"
    WORK_EXPERIENCE = "work_experience"
    SUBJECTS_ELECTIVES = "subjects_electives"
    TECHNICAL_PROFICIENCY = "technical_proficiency"
    AWARDS_RECOGNITIONS = "awards_recognitions"
    CERTIFICATIONS = "certifications"
    POSITIONS_OF_RESPONSIBILITY = "positions_of_responsibility"
    PUBLICATIONS = "publications"


class EvidenceGuidanceRequest(ContractModel):
    target_track: CareerTrack
    normalized_job: NormalizedJobDescriptionResponse
    coverage: CoverageEvaluationRequest
    resume_template_id: Literal["bits-superset-v1"]

    @model_validator(mode="after")
    def track_matches_opportunity(self) -> Self:
        tracks = self.normalized_job.tracks
        opportunity_kind = self.normalized_job.opportunity_kind
        if len(tracks) != len(set(tracks)):
            raise ValueError("normalized job tracks must be unique")
        if opportunity_kind is OpportunityKind.STATION_PROJECT:
            if tracks != (CareerTrack.PS2,):
                raise ValueError("station projects require only the PS-II track")
        elif opportunity_kind is OpportunityKind.INTERNSHIP:
            if not set(tracks) <= {CareerTrack.SI, CareerTrack.OFF_CAMPUS}:
                raise ValueError("internships require only SI or off-campus tracks")
        elif not set(tracks) <= {CareerTrack.PLACEMENT, CareerTrack.OFF_CAMPUS}:
            raise ValueError("jobs require only placement or off-campus tracks")
        if self.target_track not in self.normalized_job.tracks:
            raise ValueError("target track must be declared by the normalized job")
        allowed_opportunities = {
            CareerTrack.SI: {OpportunityKind.INTERNSHIP},
            CareerTrack.PS2: {OpportunityKind.STATION_PROJECT},
            CareerTrack.PLACEMENT: {OpportunityKind.JOB},
            CareerTrack.OFF_CAMPUS: {
                OpportunityKind.INTERNSHIP,
                OpportunityKind.JOB,
            },
        }
        if self.normalized_job.opportunity_kind not in allowed_opportunities[self.target_track]:
            raise ValueError("target track and opportunity kind are incompatible")
        return self


class ResumeGuidanceAction(ContractModel):
    evidence_claim_id: Identifier
    supports_requirement_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=250)
    section_key: ResumeSectionKey
    rank: int = Field(ge=1, le=500)
    action: Literal[ResumeActionKind.SURFACE_EVIDENCE] = ResumeActionKind.SURFACE_EVIDENCE
    student_confirmation_required: Literal[True] = True


class PathwayGuidanceAction(ContractModel):
    unit_id: str = Field(min_length=2, max_length=106)
    requirement_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=50)
    evidence_claim_ids: tuple[Identifier, ...] = Field(default=(), max_length=500)
    priority: RequirementPriority
    coverage_status: Literal[
        CoverageStatus.NEEDS_CONFIRMATION,
        CoverageStatus.MISSING,
    ]
    action: PathwayActionKind
    resume_eligible: Literal[False] = False
    rank: int = Field(ge=1, le=350)

    @model_validator(mode="after")
    def action_matches_status(self) -> Self:
        if self.coverage_status is CoverageStatus.NEEDS_CONFIRMATION:
            expected_action = PathwayActionKind.VERIFY_EVIDENCE
        elif self.evidence_claim_ids:
            expected_action = PathwayActionKind.VERIFY_AND_BUILD_EVIDENCE
        else:
            expected_action = PathwayActionKind.BUILD_EVIDENCE
        if self.action is not expected_action:
            raise ValueError("pathway action does not match coverage status")
        return self


class EvidenceGuidanceResponse(ContractModel):
    target_track: CareerTrack
    source_verification: PostingVerification
    catalog_eligibility: CatalogEligibility
    practice_only: bool
    resume_template_id: Literal["bits-superset-v1"]
    resume_actions: tuple[ResumeGuidanceAction, ...] = Field(max_length=500)
    pathway_actions: tuple[PathwayGuidanceAction, ...] = Field(max_length=350)
    coverage_summary: CoverageSummary
    guidance_version: Literal["evidence-guidance-v1"] = "evidence-guidance-v1"
    deterministic: Literal[True] = True
    student_confirmation_required: Literal[True] = True
