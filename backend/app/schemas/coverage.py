from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from app.schemas.base import ContractModel


class RequirementPriority(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class RequirementGroupOperator(StrEnum):
    ALL_OF = "all_of"
    ANY_OF = "any_of"


class CoverageStatus(StrEnum):
    SUPPORTED = "supported"
    NEEDS_CONFIRMATION = "needs_confirmation"
    MISSING = "missing"


class EvidenceKind(StrEnum):
    PROJECT = "project"
    INTERNSHIP = "internship"
    WORK_EXPERIENCE = "work_experience"
    COURSEWORK = "coursework"
    SKILL = "skill"
    ACHIEVEMENT = "achievement"
    CERTIFICATION = "certification"
    POSITION_OF_RESPONSIBILITY = "position_of_responsibility"
    RESEARCH = "research"
    PRACTICE_SCHOOL = "practice_school"


Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,99}$")]


class Requirement(ContractModel):
    id: Identifier
    statement: str = Field(min_length=5, max_length=2_000)
    priority: RequirementPriority
    group_id: Identifier | None = None


class RequirementGroup(ContractModel):
    id: Identifier
    label: str = Field(min_length=5, max_length=300)
    operator: RequirementGroupOperator
    priority: RequirementPriority
    requirement_ids: tuple[Identifier, ...] = Field(min_length=2, max_length=50)
    minimum_satisfied: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def group_semantics_are_consistent(self) -> "RequirementGroup":
        if len(self.requirement_ids) != len(set(self.requirement_ids)):
            raise ValueError("requirement_ids must be unique within a group")
        if self.operator is RequirementGroupOperator.ALL_OF:
            if self.minimum_satisfied not in {None, len(self.requirement_ids)}:
                raise ValueError("all_of minimum_satisfied must equal group size when provided")
        elif self.minimum_satisfied is not None and self.minimum_satisfied > len(
            self.requirement_ids
        ):
            raise ValueError("minimum_satisfied cannot exceed group size")
        return self


class EvidenceClaim(ContractModel):
    id: Identifier
    kind: EvidenceKind
    statement: str = Field(min_length=5, max_length=4_000)


class RequirementMatch(ContractModel):
    requirement_id: Identifier
    evidence_claim_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    confidence: float = Field(ge=0, le=1)
    verified: bool


class CoverageEvaluationRequest(ContractModel):
    requirements: tuple[Requirement, ...] = Field(min_length=1, max_length=250)
    groups: tuple[RequirementGroup, ...] = Field(default=(), max_length=100)
    evidence_claims: tuple[EvidenceClaim, ...] = Field(default=(), max_length=500)
    matches: tuple[RequirementMatch, ...] = Field(default=(), max_length=250)

    @model_validator(mode="after")
    def references_are_consistent(self) -> "CoverageEvaluationRequest":
        requirement_ids = [requirement.id for requirement in self.requirements]
        group_ids = [group.id for group in self.groups]
        evidence_ids = [claim.id for claim in self.evidence_claims]
        match_ids = [match.requirement_id for match in self.matches]
        if len(requirement_ids) != len(set(requirement_ids)):
            raise ValueError("requirement ids must be unique")
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("group ids must be unique")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence claim ids must be unique")
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("each requirement can have at most one match")

        requirements_by_id = {requirement.id: requirement for requirement in self.requirements}
        requirement_id_set = set(requirement_ids)
        group_id_set = set(group_ids)
        evidence_id_set = set(evidence_ids)
        groups_by_id = {group.id: group for group in self.groups}

        for requirement in self.requirements:
            if requirement.group_id is None:
                continue
            if requirement.group_id not in group_id_set:
                raise ValueError("requirement references an unknown group")
            if requirement.id not in groups_by_id[requirement.group_id].requirement_ids:
                raise ValueError("group does not include its referenced requirement")

        for group in self.groups:
            if not set(group.requirement_ids).issubset(requirement_id_set):
                raise ValueError("group references an unknown requirement")
            for requirement_id in group.requirement_ids:
                requirement = requirements_by_id[requirement_id]
                if requirement.group_id != group.id:
                    raise ValueError("group membership must be declared on both sides")
                if requirement.priority != group.priority:
                    raise ValueError("group and member priorities must match")

        for match in self.matches:
            if match.requirement_id not in requirement_id_set:
                raise ValueError("match references an unknown requirement")
            if not set(match.evidence_claim_ids).issubset(evidence_id_set):
                raise ValueError("match references an unknown evidence claim")
        return self


class RequirementCoverageResult(ContractModel):
    requirement_id: Identifier
    status: CoverageStatus
    evidence_claim_ids: tuple[Identifier, ...]


class GroupCoverageResult(ContractModel):
    group_id: Identifier
    status: CoverageStatus
    supported_requirement_ids: tuple[Identifier, ...]


class CoverageSummary(ContractModel):
    supported_units: int = Field(ge=0)
    needs_confirmation_units: int = Field(ge=0)
    missing_units: int = Field(ge=0)
    required_missing: int = Field(ge=0)
    preferred_missing: int = Field(ge=0)


class CoverageEvaluationResponse(ContractModel):
    requirement_results: tuple[RequirementCoverageResult, ...]
    group_results: tuple[GroupCoverageResult, ...]
    actionable_gap_ids: tuple[str, ...]
    summary: CoverageSummary
