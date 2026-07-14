from collections import defaultdict
from typing import Literal

from pydantic import SecretStr

from app.schemas.coverage import (
    CoverageStatus,
    EvidenceClaim,
    EvidenceKind,
    GroupCoverageResult,
    Requirement,
    RequirementCoverageResult,
    RequirementPriority,
)
from app.schemas.domain import CareerTrack
from app.schemas.evidence_guidance import (
    EvidenceGuidanceRequest,
    EvidenceGuidanceResponse,
    PathwayActionKind,
    PathwayGuidanceAction,
    ResumeGuidanceAction,
    ResumeSectionKey,
)
from app.schemas.job_sources import (
    OFFICIAL_SOURCE_IDS,
    SOURCE_SCHEMA_VERSIONS,
    CatalogEligibility,
    JobDescriptionNormalizationRequest,
    JobSourceId,
    NormalizedJobDescriptionResponse,
    PermissionBasis,
    normalize_human_text,
)
from app.services.catalog import get_resume_template
from app.services.coverage import evaluate_coverage
from app.services.job_sources import SOURCE_RESULTS, normalize_job_description


class EvidenceGuidanceError(ValueError):
    pass


SECTION_BY_EVIDENCE_KIND = {
    EvidenceKind.PROJECT: ResumeSectionKey.PROJECTS,
    EvidenceKind.INTERNSHIP: ResumeSectionKey.INTERNSHIPS,
    EvidenceKind.PRACTICE_SCHOOL: ResumeSectionKey.INTERNSHIPS,
    EvidenceKind.WORK_EXPERIENCE: ResumeSectionKey.WORK_EXPERIENCE,
    EvidenceKind.COURSEWORK: ResumeSectionKey.SUBJECTS_ELECTIVES,
    EvidenceKind.SKILL: ResumeSectionKey.TECHNICAL_PROFICIENCY,
    EvidenceKind.ACHIEVEMENT: ResumeSectionKey.AWARDS_RECOGNITIONS,
    EvidenceKind.CERTIFICATION: ResumeSectionKey.CERTIFICATIONS,
    EvidenceKind.POSITION_OF_RESPONSIBILITY: ResumeSectionKey.POSITIONS_OF_RESPONSIBILITY,
    EvidenceKind.RESEARCH: ResumeSectionKey.PUBLICATIONS,
}

EXACT_PERMISSION_BY_SOURCE = {
    JobSourceId.USER_UPLOAD: PermissionBasis.USER_PROVIDED,
    JobSourceId.CAMPUS_AUTHORIZED: PermissionBasis.PLACEMENT_CELL_AUTHORIZED,
    JobSourceId.SYNTHETIC_PRACTICE: PermissionBasis.INTERNAL_PRACTICE,
}

type ActionableCoverageStatus = Literal[
    CoverageStatus.NEEDS_CONFIRMATION,
    CoverageStatus.MISSING,
]


def build_evidence_guidance(
    payload: EvidenceGuidanceRequest,
) -> EvidenceGuidanceResponse:
    """Build guidance from normalized jobs and evidence artifacts owned by the server."""
    _validate_source(payload.normalized_job)
    _validate_requirements_are_grounded(payload)
    section_keys = {
        section.key for section in get_resume_template(payload.resume_template_id).sections
    }
    if not {section.value for section in SECTION_BY_EVIDENCE_KIND.values()} <= section_keys:
        raise EvidenceGuidanceError("resume template is missing a guidance section")

    evaluation = evaluate_coverage(payload.coverage)
    requirements_by_id = {
        requirement.id: requirement for requirement in payload.coverage.requirements
    }
    claims_by_id = {claim.id: claim for claim in payload.coverage.evidence_claims}
    results_by_id = {result.requirement_id: result for result in evaluation.requirement_results}

    resume_actions = _build_resume_actions(
        requirements_by_id,
        claims_by_id,
        evaluation.requirement_results,
    )
    pathway_actions = _build_pathway_actions(
        payload,
        requirements_by_id,
        results_by_id,
        evaluation.group_results,
    )
    source = payload.normalized_job.source
    return EvidenceGuidanceResponse(
        target_track=payload.target_track,
        source_verification=source.verification,
        catalog_eligibility=source.catalog_eligibility,
        practice_only=source.catalog_eligibility is CatalogEligibility.PRACTICE_ONLY,
        resume_template_id=payload.resume_template_id,
        resume_actions=resume_actions,
        pathway_actions=pathway_actions,
        coverage_summary=evaluation.summary,
    )


def _validate_source(job: NormalizedJobDescriptionResponse) -> None:
    source = job.source
    expected_access, expected_verification, expected_eligibility = SOURCE_RESULTS[source.source_id]
    if (
        source.access_level is not expected_access
        or source.verification is not expected_verification
        or source.catalog_eligibility is not expected_eligibility
        or source.schema_version != SOURCE_SCHEMA_VERSIONS[source.source_id]
    ):
        raise EvidenceGuidanceError("normalized source metadata is inconsistent")

    required_permission = EXACT_PERMISSION_BY_SOURCE.get(source.source_id)
    if required_permission is not None and source.permission_basis is not required_permission:
        raise EvidenceGuidanceError("normalized source permission is inconsistent")
    if source.source_id in OFFICIAL_SOURCE_IDS:
        if source.permission_basis not in {
            PermissionBasis.EMPLOYER_AUTHORIZED,
            PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
        }:
            raise EvidenceGuidanceError("official source permission is inconsistent")
        if set(job.tracks) != {CareerTrack.OFF_CAMPUS}:
            raise EvidenceGuidanceError("official sources are restricted to off-campus guidance")
    elif source.source_id is JobSourceId.CAMPUS_AUTHORIZED and CareerTrack.OFF_CAMPUS in job.tracks:
        raise EvidenceGuidanceError("campus sources cannot be relabelled as off-campus")

    normalized = _renormalize_job(job)
    if normalized != job:
        raise EvidenceGuidanceError("normalized job does not match its canonical representation")


def _renormalize_job(
    job: NormalizedJobDescriptionResponse,
) -> NormalizedJobDescriptionResponse:
    source = job.source
    request_data: dict[str, object] = {
        "source_id": source.source_id,
        "permission_basis": source.permission_basis,
        "source_account": source.source_account,
        "external_id": source.external_id,
        "source_url": source.source_url,
        "schema_version": (
            None if source.source_id is JobSourceId.USER_UPLOAD else source.schema_version
        ),
        "observed_at": source.observed_at,
        "organization": job.organization,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "tracks": job.tracks,
        "opportunity_kind": job.opportunity_kind,
        "application_url": job.application_url,
        "published_at": job.published_at,
        "application_deadline": job.application_deadline,
    }
    if source.source_id is JobSourceId.CAMPUS_AUTHORIZED:
        request_data["authorization_ref"] = SecretStr("canonical-campus-source")
    try:
        request = JobDescriptionNormalizationRequest.model_validate(request_data)
        return normalize_job_description(request)
    except ValueError as exc:
        raise EvidenceGuidanceError("normalized job provenance is invalid") from exc


def _validate_requirements_are_grounded(payload: EvidenceGuidanceRequest) -> None:
    description = normalize_human_text(payload.normalized_job.description).casefold()
    for requirement in payload.coverage.requirements:
        statement = normalize_human_text(requirement.statement).casefold()
        if statement not in description:
            raise EvidenceGuidanceError(
                "coverage requirement is not grounded in the job description"
            )


def _build_resume_actions(
    requirements_by_id: dict[str, Requirement],
    claims_by_id: dict[str, EvidenceClaim],
    requirement_results: tuple[RequirementCoverageResult, ...],
) -> tuple[ResumeGuidanceAction, ...]:
    requirement_ids_by_claim: defaultdict[str, set[str]] = defaultdict(set)
    for result in requirement_results:
        if result.status is not CoverageStatus.SUPPORTED:
            continue
        for claim_id in result.evidence_claim_ids:
            requirement_ids_by_claim[claim_id].add(result.requirement_id)

    ordered_claim_ids = sorted(
        requirement_ids_by_claim,
        key=lambda claim_id: _resume_sort_key(
            claim_id,
            requirement_ids_by_claim[claim_id],
            requirements_by_id,
        ),
    )
    actions: list[ResumeGuidanceAction] = []
    for rank, claim_id in enumerate(ordered_claim_ids, start=1):
        claim = claims_by_id[claim_id]
        requirement_ids = tuple(
            sorted(
                requirement_ids_by_claim[claim_id],
                key=lambda requirement_id: (
                    _priority_rank(requirements_by_id[requirement_id].priority),
                    requirement_id,
                ),
            )
        )
        actions.append(
            ResumeGuidanceAction(
                evidence_claim_id=claim_id,
                supports_requirement_ids=requirement_ids,
                section_key=SECTION_BY_EVIDENCE_KIND[claim.kind],
                rank=rank,
            )
        )
    return tuple(actions)


def _resume_sort_key(
    claim_id: str,
    requirement_ids: set[str],
    requirements_by_id: dict[str, Requirement],
) -> tuple[int, int, int, str]:
    required_count = sum(
        requirements_by_id[requirement_id].priority is RequirementPriority.REQUIRED
        for requirement_id in requirement_ids
    )
    return (
        0 if required_count else 1,
        -required_count,
        -len(requirement_ids),
        claim_id,
    )


def _build_pathway_actions(
    payload: EvidenceGuidanceRequest,
    requirements_by_id: dict[str, Requirement],
    results_by_id: dict[str, RequirementCoverageResult],
    group_results: tuple[GroupCoverageResult, ...],
) -> tuple[PathwayGuidanceAction, ...]:
    grouped_requirement_ids = {
        requirement_id
        for group in payload.coverage.groups
        for requirement_id in group.requirement_ids
    }
    candidates: list[
        tuple[
            str,
            tuple[str, ...],
            tuple[str, ...],
            RequirementPriority,
            ActionableCoverageStatus,
        ]
    ] = []
    for requirement_id, result in results_by_id.items():
        if requirement_id in grouped_requirement_ids or result.status is CoverageStatus.SUPPORTED:
            continue
        requirement = requirements_by_id[requirement_id]
        candidates.append(
            (
                requirement_id,
                (requirement_id,),
                tuple(sorted(result.evidence_claim_ids)),
                requirement.priority,
                _actionable_status(result.status),
            )
        )

    groups_by_id = {group.id: group for group in payload.coverage.groups}
    for group_result in group_results:
        if group_result.status is CoverageStatus.SUPPORTED:
            continue
        group = groups_by_id[group_result.group_id]
        requirement_ids = tuple(sorted(group.requirement_ids))
        evidence_claim_ids = tuple(
            sorted(
                {
                    claim_id
                    for requirement_id in requirement_ids
                    if results_by_id[requirement_id].status is CoverageStatus.NEEDS_CONFIRMATION
                    for claim_id in results_by_id[requirement_id].evidence_claim_ids
                }
            )
        )
        candidates.append(
            (
                f"group:{group.id}",
                requirement_ids,
                evidence_claim_ids,
                group.priority,
                _actionable_status(group_result.status),
            )
        )

    ordered = sorted(
        candidates,
        key=lambda item: (
            _priority_rank(item[3]),
            _pathway_action_rank(item[4], item[2]),
            item[0],
        ),
    )
    return tuple(
        PathwayGuidanceAction(
            unit_id=unit_id,
            requirement_ids=requirement_ids,
            evidence_claim_ids=evidence_claim_ids,
            priority=priority,
            coverage_status=status,
            action=(
                PathwayActionKind.VERIFY_EVIDENCE
                if status is CoverageStatus.NEEDS_CONFIRMATION
                else (
                    PathwayActionKind.VERIFY_AND_BUILD_EVIDENCE
                    if evidence_claim_ids
                    else PathwayActionKind.BUILD_EVIDENCE
                )
            ),
            rank=rank,
        )
        for rank, (
            unit_id,
            requirement_ids,
            evidence_claim_ids,
            priority,
            status,
        ) in enumerate(ordered, start=1)
    )


def _priority_rank(priority: RequirementPriority) -> int:
    return 0 if priority is RequirementPriority.REQUIRED else 1


def _pathway_action_rank(
    status: ActionableCoverageStatus,
    evidence_claim_ids: tuple[str, ...],
) -> int:
    if status is CoverageStatus.NEEDS_CONFIRMATION:
        return 0
    return 1 if evidence_claim_ids else 2


def _actionable_status(status: CoverageStatus) -> ActionableCoverageStatus:
    if status is CoverageStatus.NEEDS_CONFIRMATION:
        return CoverageStatus.NEEDS_CONFIRMATION
    if status is CoverageStatus.MISSING:
        return CoverageStatus.MISSING
    raise EvidenceGuidanceError("supported coverage cannot become a pathway action")
