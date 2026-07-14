from datetime import UTC, datetime

import pytest
from app.schemas.evidence_guidance import (
    EvidenceGuidanceRequest,
    PathwayActionKind,
    ResumeActionKind,
    ResumeSectionKey,
)
from app.services.evidence_guidance import EvidenceGuidanceError, build_evidence_guidance
from pydantic import SecretStr, ValidationError

from app.schemas.coverage import (
    CoverageEvaluationRequest,
    EvidenceClaim,
    EvidenceKind,
    Requirement,
    RequirementGroup,
    RequirementGroupOperator,
    RequirementMatch,
    RequirementPriority,
)
from app.schemas.domain import CareerTrack, OpportunityKind
from app.schemas.job_sources import (
    SOURCE_SCHEMA_VERSIONS,
    JobDescriptionNormalizationRequest,
    JobSourceId,
    PermissionBasis,
    PostingVerification,
)
from app.services.job_sources import normalize_job_description

OBSERVED_AT = datetime(2026, 7, 13, 12, tzinfo=UTC)
BACKEND_REQUIREMENT = "Build backend services with Python and FastAPI."
DSA_REQUIREMENT = "Solve algorithms and data structures problems in technical interviews."
VOICE_REQUIREMENT = "Demonstrate project evidence relevant to voice intelligence."
WEB_REQUIREMENT = "Demonstrate project evidence relevant to server technology or web systems."
PROJECT_EVIDENCE = "Built and deployed a FastAPI web service for 500 student records."
ACHIEVEMENT_EVIDENCE = "Won first place in the campus software engineering hackathon."
JD_DESCRIPTION = (
    "Developer internship responsibilities. "
    f"{BACKEND_REQUIREMENT} {DSA_REQUIREMENT} {VOICE_REQUIREMENT} {WEB_REQUIREMENT} "
    "Candidates collaborate with engineers and write tested production code."
)


def normalized_job(
    track: CareerTrack = CareerTrack.SI,
    opportunity_kind: OpportunityKind = OpportunityKind.INTERNSHIP,
    source_id: JobSourceId = JobSourceId.USER_UPLOAD,
):
    data: dict[str, object] = {
        "source_id": source_id,
        "permission_basis": PermissionBasis.USER_PROVIDED,
        "observed_at": OBSERVED_AT,
        "organization": "Example Systems",
        "title": "Developer Intern",
        "description": JD_DESCRIPTION,
        "tracks": (track,),
        "opportunity_kind": opportunity_kind,
    }
    if source_id is JobSourceId.CAMPUS_AUTHORIZED:
        data.update(
            permission_basis=PermissionBasis.PLACEMENT_CELL_AUTHORIZED,
            source_account="bits-pilani",
            external_id="si-example-1",
            authorization_ref=SecretStr("placement-cell-authorized-export-2026"),
        )
    elif source_id is JobSourceId.SYNTHETIC_PRACTICE:
        data.update(
            permission_basis=PermissionBasis.INTERNAL_PRACTICE,
            source_account="gradpath-samples-v1",
            external_id="practice-example-1",
            schema_version=SOURCE_SCHEMA_VERSIONS[JobSourceId.SYNTHETIC_PRACTICE],
        )
    elif source_id is JobSourceId.GREENHOUSE:
        data.update(
            permission_basis=PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
            source_account="example",
            external_id="7982460",
            source_url="https://boards.greenhouse.io/example/jobs/7982460",
            schema_version=SOURCE_SCHEMA_VERSIONS[JobSourceId.GREENHOUSE],
        )
    return normalize_job_description(JobDescriptionNormalizationRequest.model_validate(data))


def simple_coverage(
    *,
    verified: bool = True,
    confidence: float = 0.95,
) -> CoverageEvaluationRequest:
    return CoverageEvaluationRequest(
        requirements=(
            Requirement(
                id="backend",
                statement=BACKEND_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
            ),
            Requirement(
                id="dsa",
                statement=DSA_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
            ),
        ),
        evidence_claims=(
            EvidenceClaim(
                id="project-api",
                kind=EvidenceKind.PROJECT,
                statement=PROJECT_EVIDENCE,
            ),
        ),
        matches=(
            RequirementMatch(
                requirement_id="backend",
                evidence_claim_ids=("project-api",),
                confidence=confidence,
                verified=verified,
            ),
        ),
    )


def guidance_request(
    *,
    track: CareerTrack = CareerTrack.SI,
    job=None,
    coverage: CoverageEvaluationRequest | None = None,
) -> EvidenceGuidanceRequest:
    return EvidenceGuidanceRequest(
        target_track=track,
        normalized_job=job or normalized_job(track=track),
        coverage=coverage or simple_coverage(),
        resume_template_id="bits-superset-v1",
    )


def test_supported_project_becomes_a_cited_resume_surface_action() -> None:
    result = build_evidence_guidance(guidance_request())

    assert len(result.resume_actions) == 1
    action = result.resume_actions[0]
    assert action.evidence_claim_id == "project-api"
    assert action.supports_requirement_ids == ("backend",)
    assert action.section_key is ResumeSectionKey.PROJECTS
    assert action.action is ResumeActionKind.SURFACE_EVIDENCE
    assert action.rank == 1
    assert action.student_confirmation_required is True
    assert result.coverage_summary.supported_units == 1


def test_shared_claim_is_deduplicated_and_required_evidence_ranks_first() -> None:
    coverage = CoverageEvaluationRequest(
        requirements=(
            Requirement(
                id="backend",
                statement=BACKEND_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
            ),
            Requirement(
                id="python",
                statement="Build backend services with Python and FastAPI.",
                priority=RequirementPriority.PREFERRED,
            ),
            Requirement(
                id="leadership",
                statement="Candidates collaborate with engineers and write tested production code.",
                priority=RequirementPriority.PREFERRED,
            ),
        ),
        evidence_claims=(
            EvidenceClaim(
                id="project-api",
                kind=EvidenceKind.PROJECT,
                statement=PROJECT_EVIDENCE,
            ),
            EvidenceClaim(
                id="award",
                kind=EvidenceKind.ACHIEVEMENT,
                statement=ACHIEVEMENT_EVIDENCE,
            ),
        ),
        matches=(
            RequirementMatch(
                requirement_id="python",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=True,
            ),
            RequirementMatch(
                requirement_id="backend",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=True,
            ),
            RequirementMatch(
                requirement_id="leadership",
                evidence_claim_ids=("award",),
                confidence=0.95,
                verified=True,
            ),
        ),
    )

    result = build_evidence_guidance(guidance_request(coverage=coverage))

    assert [action.evidence_claim_id for action in result.resume_actions] == [
        "project-api",
        "award",
    ]
    assert result.resume_actions[0].supports_requirement_ids == ("backend", "python")
    assert result.resume_actions[1].section_key is ResumeSectionKey.AWARDS_RECOGNITIONS


@pytest.mark.parametrize(
    ("verified", "confidence"),
    [(False, 0.95), (True, 0.6)],
)
def test_unverified_or_low_confidence_evidence_becomes_verify_only(
    verified: bool,
    confidence: float,
) -> None:
    result = build_evidence_guidance(
        guidance_request(coverage=simple_coverage(verified=verified, confidence=confidence))
    )

    assert result.resume_actions == ()
    backend_action = next(
        action for action in result.pathway_actions if action.unit_id == "backend"
    )
    assert backend_action.action is PathwayActionKind.VERIFY_EVIDENCE
    assert backend_action.evidence_claim_ids == ("project-api",)
    assert backend_action.resume_eligible is False


def test_missing_requirement_becomes_future_only_build_action() -> None:
    result = build_evidence_guidance(guidance_request())

    dsa_action = next(action for action in result.pathway_actions if action.unit_id == "dsa")
    assert dsa_action.action is PathwayActionKind.BUILD_EVIDENCE
    assert dsa_action.requirement_ids == ("dsa",)
    assert dsa_action.evidence_claim_ids == ()
    assert dsa_action.resume_eligible is False


def grouped_coverage(*, verified: bool | None) -> CoverageEvaluationRequest:
    matches = (
        (
            RequirementMatch(
                requirement_id="web",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=verified,
            ),
        )
        if verified is not None
        else ()
    )
    return CoverageEvaluationRequest(
        requirements=(
            Requirement(
                id="voice",
                statement=VOICE_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
                group_id="coe",
            ),
            Requirement(
                id="web",
                statement=WEB_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
                group_id="coe",
            ),
        ),
        groups=(
            RequirementGroup(
                id="coe",
                label="At least one engineering centre of excellence",
                operator=RequirementGroupOperator.ANY_OF,
                priority=RequirementPriority.REQUIRED,
                requirement_ids=("voice", "web"),
                minimum_satisfied=1,
            ),
        ),
        evidence_claims=(
            EvidenceClaim(
                id="project-api",
                kind=EvidenceKind.PROJECT,
                statement=PROJECT_EVIDENCE,
            ),
        ),
        matches=matches,
    )


def test_supported_any_of_group_suppresses_unmatched_alternatives() -> None:
    result = build_evidence_guidance(guidance_request(coverage=grouped_coverage(verified=True)))

    assert result.pathway_actions == ()
    assert result.resume_actions[0].supports_requirement_ids == ("web",)


@pytest.mark.parametrize(
    ("verified", "expected_action", "expected_evidence"),
    [
        (False, PathwayActionKind.VERIFY_EVIDENCE, ("project-api",)),
        (None, PathwayActionKind.BUILD_EVIDENCE, ()),
    ],
)
def test_unsatisfied_any_of_group_produces_one_group_level_action(
    verified: bool | None,
    expected_action: PathwayActionKind,
    expected_evidence: tuple[str, ...],
) -> None:
    result = build_evidence_guidance(guidance_request(coverage=grouped_coverage(verified=verified)))

    assert len(result.pathway_actions) == 1
    action = result.pathway_actions[0]
    assert action.unit_id == "group:coe"
    assert action.requirement_ids == ("voice", "web")
    assert action.action is expected_action
    assert action.evidence_claim_ids == expected_evidence


def test_equivalent_permuted_inputs_produce_identical_output() -> None:
    coverage = simple_coverage()
    permuted = CoverageEvaluationRequest(
        requirements=tuple(reversed(coverage.requirements)),
        groups=coverage.groups,
        evidence_claims=tuple(reversed(coverage.evidence_claims)),
        matches=tuple(reversed(coverage.matches)),
    )

    baseline = build_evidence_guidance(guidance_request(coverage=coverage))
    reordered = build_evidence_guidance(guidance_request(coverage=permuted))

    assert baseline.model_dump_json() == reordered.model_dump_json()


def test_response_omits_raw_job_evidence_urls_and_fingerprints() -> None:
    job = normalized_job(
        track=CareerTrack.OFF_CAMPUS,
        opportunity_kind=OpportunityKind.INTERNSHIP,
        source_id=JobSourceId.GREENHOUSE,
    )

    result = build_evidence_guidance(guidance_request(track=CareerTrack.OFF_CAMPUS, job=job))
    serialized = result.model_dump_json()

    for forbidden in (
        JD_DESCRIPTION,
        BACKEND_REQUIREMENT,
        PROJECT_EVIDENCE,
        "boards.greenhouse.io",
        job.content_fingerprint,
        job.source.source_locator_fingerprint,
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("track", "opportunity_kind"),
    [
        (CareerTrack.SI, OpportunityKind.INTERNSHIP),
        (CareerTrack.PS2, OpportunityKind.STATION_PROJECT),
        (CareerTrack.PLACEMENT, OpportunityKind.JOB),
        (CareerTrack.OFF_CAMPUS, OpportunityKind.INTERNSHIP),
        (CareerTrack.OFF_CAMPUS, OpportunityKind.JOB),
    ],
)
def test_valid_track_opportunity_combinations_are_preserved(
    track: CareerTrack,
    opportunity_kind: OpportunityKind,
) -> None:
    job = normalized_job(track=track, opportunity_kind=opportunity_kind)

    result = build_evidence_guidance(guidance_request(track=track, job=job))

    assert result.target_track is track


@pytest.mark.parametrize(
    ("track", "opportunity_kind"),
    [
        (CareerTrack.SI, OpportunityKind.JOB),
        (CareerTrack.PS2, OpportunityKind.INTERNSHIP),
        (CareerTrack.PLACEMENT, OpportunityKind.INTERNSHIP),
        (CareerTrack.OFF_CAMPUS, OpportunityKind.STATION_PROJECT),
    ],
)
def test_invalid_track_opportunity_combinations_are_rejected(
    track: CareerTrack,
    opportunity_kind: OpportunityKind,
) -> None:
    forged = normalized_job().model_copy(
        update={"tracks": (track,), "opportunity_kind": opportunity_kind}
    )

    with pytest.raises(ValidationError):
        guidance_request(track=track, job=forged)


def test_target_track_must_be_declared_by_the_normalized_job() -> None:
    with pytest.raises(ValidationError):
        guidance_request(track=CareerTrack.PLACEMENT, job=normalized_job())


def test_official_and_campus_sources_cannot_cross_trust_boundaries() -> None:
    official = normalized_job(
        track=CareerTrack.OFF_CAMPUS,
        opportunity_kind=OpportunityKind.INTERNSHIP,
        source_id=JobSourceId.GREENHOUSE,
    ).model_copy(update={"tracks": (CareerTrack.SI,)})
    campus = normalized_job(source_id=JobSourceId.CAMPUS_AUTHORIZED).model_copy(
        update={"tracks": (CareerTrack.OFF_CAMPUS,)}
    )

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(track=CareerTrack.SI, job=official))
    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(track=CareerTrack.OFF_CAMPUS, job=campus))


def test_forged_normalized_source_metadata_is_rejected() -> None:
    job = normalized_job()
    forged_source = job.source.model_copy(
        update={"verification": PostingVerification.PROVIDER_RECORD}
    )
    forged = job.model_copy(update={"source": forged_source})

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(job=forged))


def test_synthetic_source_is_explicitly_practice_only() -> None:
    job = normalized_job(source_id=JobSourceId.SYNTHETIC_PRACTICE)

    result = build_evidence_guidance(guidance_request(job=job))

    assert result.practice_only is True
    assert result.source_verification is PostingVerification.SYNTHETIC_PRACTICE


def test_unsupported_template_and_extra_fields_are_rejected() -> None:
    payload = guidance_request().model_dump()
    payload["resume_template_id"] = "invented-template"
    with pytest.raises(ValidationError):
        EvidenceGuidanceRequest.model_validate(payload)

    payload = guidance_request().model_dump()
    payload["future_field"] = True
    with pytest.raises(ValidationError):
        EvidenceGuidanceRequest.model_validate(payload)


def test_requirements_must_be_exactly_grounded_in_the_normalized_jd() -> None:
    coverage = simple_coverage()
    forged_requirement = coverage.requirements[0].model_copy(
        update={"statement": "Candidates must operate invented quantum infrastructure."}
    )
    forged_coverage = coverage.model_copy(
        update={"requirements": (forged_requirement, coverage.requirements[1])}
    )

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(coverage=forged_coverage))


def test_all_output_references_point_to_known_requirements_and_claims() -> None:
    request = guidance_request()
    result = build_evidence_guidance(request)
    requirement_ids = {requirement.id for requirement in request.coverage.requirements}
    claim_ids = {claim.id for claim in request.coverage.evidence_claims}

    for action in result.resume_actions:
        assert set(action.supports_requirement_ids) <= requirement_ids
        assert action.evidence_claim_id in claim_ids
    for action in result.pathway_actions:
        assert set(action.requirement_ids) <= requirement_ids
        assert set(action.evidence_claim_ids) <= claim_ids
