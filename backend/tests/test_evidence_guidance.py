from datetime import UTC, datetime

import pytest
from pydantic import SecretStr, ValidationError

from app.main import app
from app.schemas.coverage import (
    CoverageEvaluationRequest,
    CoverageStatus,
    EvidenceClaim,
    EvidenceKind,
    Requirement,
    RequirementGroup,
    RequirementGroupOperator,
    RequirementMatch,
    RequirementPriority,
)
from app.schemas.domain import AccessLevel, CareerTrack, OpportunityKind
from app.schemas.evidence_guidance import (
    EvidenceGuidanceRequest,
    PathwayActionKind,
    ResumeActionKind,
    ResumeSectionKey,
)
from app.schemas.job_sources import (
    SOURCE_SCHEMA_VERSIONS,
    CatalogEligibility,
    JobDescriptionNormalizationRequest,
    JobSourceId,
    NormalizedJobDescriptionResponse,
    PermissionBasis,
    PostingVerification,
)
from app.services.evidence_guidance import EvidenceGuidanceError, build_evidence_guidance
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
) -> NormalizedJobDescriptionResponse:
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
    job: NormalizedJobDescriptionResponse | None = None,
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
    coverage = CoverageEvaluationRequest(
        requirements=(
            Requirement(
                id="backend",
                statement=BACKEND_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
                group_id="stack",
            ),
            Requirement(
                id="python",
                statement=BACKEND_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
                group_id="stack",
            ),
            Requirement(
                id="dsa",
                statement=DSA_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
            ),
            Requirement(
                id="leadership",
                statement="Candidates collaborate with engineers and write tested production code.",
                priority=RequirementPriority.PREFERRED,
            ),
            Requirement(
                id="voice",
                statement=VOICE_REQUIREMENT,
                priority=RequirementPriority.PREFERRED,
                group_id="coe",
            ),
            Requirement(
                id="web",
                statement=WEB_REQUIREMENT,
                priority=RequirementPriority.PREFERRED,
                group_id="coe",
            ),
        ),
        groups=(
            RequirementGroup(
                id="stack",
                label="At least one supported backend stack requirement",
                operator=RequirementGroupOperator.ANY_OF,
                priority=RequirementPriority.REQUIRED,
                requirement_ids=("backend", "python"),
            ),
            RequirementGroup(
                id="coe",
                label="At least one engineering centre of excellence",
                operator=RequirementGroupOperator.ANY_OF,
                priority=RequirementPriority.PREFERRED,
                requirement_ids=("voice", "web"),
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
                requirement_id="backend",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=True,
            ),
            RequirementMatch(
                requirement_id="dsa",
                evidence_claim_ids=("award",),
                confidence=0.95,
                verified=False,
            ),
            RequirementMatch(
                requirement_id="leadership",
                evidence_claim_ids=("award",),
                confidence=0.95,
                verified=True,
            ),
        ),
    )
    permuted = CoverageEvaluationRequest(
        requirements=tuple(reversed(coverage.requirements)),
        groups=tuple(
            group.model_copy(update={"requirement_ids": tuple(reversed(group.requirement_ids))})
            for group in reversed(coverage.groups)
        ),
        evidence_claims=tuple(reversed(coverage.evidence_claims)),
        matches=tuple(reversed(coverage.matches)),
    )

    baseline = build_evidence_guidance(guidance_request(coverage=coverage))
    reordered = build_evidence_guidance(guidance_request(coverage=permuted))

    assert baseline.model_dump_json() == reordered.model_dump_json()
    assert [action.evidence_claim_id for action in baseline.resume_actions] == [
        "project-api",
        "award",
    ]
    assert [action.rank for action in baseline.resume_actions] == [1, 2]
    assert [action.unit_id for action in baseline.pathway_actions] == ["dsa", "group:coe"]
    assert [action.rank for action in baseline.pathway_actions] == [1, 2]


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

    dumped = result.model_dump(mode="json")
    assert set(dumped) == {
        "target_track",
        "source_verification",
        "catalog_eligibility",
        "practice_only",
        "resume_template_id",
        "resume_actions",
        "pathway_actions",
        "coverage_summary",
        "guidance_version",
        "deterministic",
        "student_confirmation_required",
    }
    assert set(dumped["resume_actions"][0]) == {
        "evidence_claim_id",
        "supports_requirement_ids",
        "section_key",
        "rank",
        "action",
        "student_confirmation_required",
    }
    assert set(dumped["pathway_actions"][0]) == {
        "unit_id",
        "requirement_ids",
        "evidence_claim_ids",
        "priority",
        "coverage_status",
        "action",
        "resume_eligible",
        "rank",
    }
    assert set(dumped["coverage_summary"]) == {
        "supported_units",
        "needs_confirmation_units",
        "missing_units",
        "required_missing",
        "preferred_missing",
    }


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


@pytest.mark.parametrize(
    ("tracks", "opportunity_kind", "target_track"),
    [
        ((CareerTrack.SI, CareerTrack.PS2), OpportunityKind.INTERNSHIP, CareerTrack.SI),
        (
            (CareerTrack.PS2, CareerTrack.SI),
            OpportunityKind.STATION_PROJECT,
            CareerTrack.PS2,
        ),
        (
            (CareerTrack.PLACEMENT, CareerTrack.SI),
            OpportunityKind.JOB,
            CareerTrack.PLACEMENT,
        ),
        ((CareerTrack.SI, CareerTrack.SI), OpportunityKind.INTERNSHIP, CareerTrack.SI),
    ],
)
def test_normalized_job_track_set_must_match_opportunity_kind(
    tracks: tuple[CareerTrack, ...],
    opportunity_kind: OpportunityKind,
    target_track: CareerTrack,
) -> None:
    forged = normalized_job().model_copy(
        update={"tracks": tracks, "opportunity_kind": opportunity_kind}
    )

    with pytest.raises(ValidationError):
        guidance_request(track=target_track, job=forged)


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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("access_level", AccessLevel.PUBLIC),
        ("verification", PostingVerification.PROVIDER_RECORD),
        ("catalog_eligibility", CatalogEligibility.PUBLIC_CATALOG),
        ("schema_version", SOURCE_SCHEMA_VERSIONS[JobSourceId.GREENHOUSE]),
        ("permission_basis", PermissionBasis.PUBLIC_API_TERMS_REVIEWED),
    ],
)
def test_each_normalized_source_trust_field_is_validated(field: str, value: object) -> None:
    job = normalized_job()
    forged = job.model_copy(update={"source": job.source.model_copy(update={field: value})})

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(job=forged))


@pytest.mark.parametrize("fingerprint_field", ["content_fingerprint", "source_fingerprint"])
def test_normalized_source_fingerprints_are_recomputed(fingerprint_field: str) -> None:
    job = normalized_job()
    forged_fingerprint = f"sha256:{'0' * 64}"
    if fingerprint_field == "content_fingerprint":
        forged = job.model_copy(update={"content_fingerprint": forged_fingerprint})
    else:
        forged = job.model_copy(
            update={
                "source": job.source.model_copy(
                    update={"source_locator_fingerprint": forged_fingerprint}
                )
            }
        )

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(job=forged))


def test_provider_source_requires_complete_canonical_identity() -> None:
    job = normalized_job(
        track=CareerTrack.OFF_CAMPUS,
        opportunity_kind=OpportunityKind.INTERNSHIP,
        source_id=JobSourceId.GREENHOUSE,
    )
    forged = job.model_copy(
        update={
            "source": job.source.model_copy(
                update={"source_account": None, "external_id": None, "source_url": None}
            )
        }
    )

    with pytest.raises(EvidenceGuidanceError):
        build_evidence_guidance(guidance_request(track=CareerTrack.OFF_CAMPUS, job=forged))


def test_synthetic_source_is_explicitly_practice_only() -> None:
    job = normalized_job(source_id=JobSourceId.SYNTHETIC_PRACTICE)

    result = build_evidence_guidance(guidance_request(job=job))

    assert result.practice_only is True
    assert result.source_verification is PostingVerification.SYNTHETIC_PRACTICE


def test_valid_campus_ps2_guidance_preserves_restricted_provenance() -> None:
    job = normalized_job(
        track=CareerTrack.PS2,
        opportunity_kind=OpportunityKind.STATION_PROJECT,
        source_id=JobSourceId.CAMPUS_AUTHORIZED,
    )

    result = build_evidence_guidance(guidance_request(track=CareerTrack.PS2, job=job))

    assert result.source_verification is PostingVerification.CAMPUS_AUTHORIZED
    assert result.catalog_eligibility is CatalogEligibility.CAMPUS_CATALOG
    assert result.practice_only is False


@pytest.mark.parametrize(
    ("evidence_kind", "expected_section"),
    [
        (EvidenceKind.PROJECT, ResumeSectionKey.PROJECTS),
        (EvidenceKind.INTERNSHIP, ResumeSectionKey.INTERNSHIPS),
        (EvidenceKind.PRACTICE_SCHOOL, ResumeSectionKey.INTERNSHIPS),
        (EvidenceKind.WORK_EXPERIENCE, ResumeSectionKey.WORK_EXPERIENCE),
        (EvidenceKind.COURSEWORK, ResumeSectionKey.SUBJECTS_ELECTIVES),
        (EvidenceKind.SKILL, ResumeSectionKey.TECHNICAL_PROFICIENCY),
        (EvidenceKind.ACHIEVEMENT, ResumeSectionKey.AWARDS_RECOGNITIONS),
        (EvidenceKind.CERTIFICATION, ResumeSectionKey.CERTIFICATIONS),
        (
            EvidenceKind.POSITION_OF_RESPONSIBILITY,
            ResumeSectionKey.POSITIONS_OF_RESPONSIBILITY,
        ),
        (EvidenceKind.RESEARCH, ResumeSectionKey.PUBLICATIONS),
    ],
)
def test_every_evidence_kind_maps_to_a_bits_section(
    evidence_kind: EvidenceKind,
    expected_section: ResumeSectionKey,
) -> None:
    coverage = CoverageEvaluationRequest(
        requirements=(
            Requirement(
                id="backend",
                statement=BACKEND_REQUIREMENT,
                priority=RequirementPriority.REQUIRED,
            ),
        ),
        evidence_claims=(
            EvidenceClaim(
                id="evidence",
                kind=evidence_kind,
                statement=PROJECT_EVIDENCE,
            ),
        ),
        matches=(
            RequirementMatch(
                requirement_id="backend",
                evidence_claim_ids=("evidence",),
                confidence=0.95,
                verified=True,
            ),
        ),
    )

    result = build_evidence_guidance(guidance_request(coverage=coverage))

    assert result.resume_actions[0].section_key is expected_section


def test_mixed_group_emits_one_verify_and_build_action() -> None:
    coverage = CoverageEvaluationRequest(
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
                label="Both engineering centre requirements",
                operator=RequirementGroupOperator.ALL_OF,
                priority=RequirementPriority.REQUIRED,
                requirement_ids=("voice", "web"),
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
                requirement_id="web",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=False,
            ),
        ),
    )

    result = build_evidence_guidance(guidance_request(coverage=coverage))

    assert len(result.pathway_actions) == 1
    action = result.pathway_actions[0]
    assert action.coverage_status is CoverageStatus.MISSING
    assert action.action is PathwayActionKind.VERIFY_AND_BUILD_EVIDENCE
    assert action.evidence_claim_ids == ("project-api",)


def test_threshold_group_needing_confirmation_cites_only_unverified_evidence() -> None:
    coverage = CoverageEvaluationRequest(
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
                label="Both engineering centre requirements",
                operator=RequirementGroupOperator.ANY_OF,
                priority=RequirementPriority.REQUIRED,
                requirement_ids=("voice", "web"),
                minimum_satisfied=2,
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
                requirement_id="voice",
                evidence_claim_ids=("project-api",),
                confidence=0.95,
                verified=True,
            ),
            RequirementMatch(
                requirement_id="web",
                evidence_claim_ids=("award",),
                confidence=0.95,
                verified=False,
            ),
        ),
    )

    result = build_evidence_guidance(guidance_request(coverage=coverage))

    assert len(result.pathway_actions) == 1
    action = result.pathway_actions[0]
    assert action.coverage_status is CoverageStatus.NEEDS_CONFIRMATION
    assert action.action is PathwayActionKind.VERIFY_EVIDENCE
    assert action.evidence_claim_ids == ("award",)


def test_duplicate_evidence_references_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RequirementMatch(
            requirement_id="backend",
            evidence_claim_ids=("project-api", "project-api"),
            confidence=0.95,
            verified=False,
        )


def test_guidance_core_has_no_http_route_until_server_owned_artifacts_exist() -> None:
    route_paths = {str(getattr(route, "path", "")) for route in app.routes}

    assert not any("guidance" in path for path in route_paths)


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
