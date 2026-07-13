from app.schemas.coverage import (
    CoverageEvaluationRequest,
    CoverageEvaluationResponse,
    CoverageStatus,
    CoverageSummary,
    GroupCoverageResult,
    RequirementCoverageResult,
    RequirementGroupOperator,
    RequirementPriority,
)

SUPPORTED_CONFIDENCE = 0.8


def evaluate_coverage(payload: CoverageEvaluationRequest) -> CoverageEvaluationResponse:
    matches_by_requirement = {match.requirement_id: match for match in payload.matches}
    requirement_results: list[RequirementCoverageResult] = []
    for requirement in payload.requirements:
        match = matches_by_requirement.get(requirement.id)
        if match is None:
            coverage_status = CoverageStatus.MISSING
            evidence_claim_ids: tuple[str, ...] = ()
        elif match.verified and match.confidence >= SUPPORTED_CONFIDENCE:
            coverage_status = CoverageStatus.SUPPORTED
            evidence_claim_ids = match.evidence_claim_ids
        else:
            coverage_status = CoverageStatus.NEEDS_CONFIRMATION
            evidence_claim_ids = match.evidence_claim_ids
        requirement_results.append(
            RequirementCoverageResult(
                requirement_id=requirement.id,
                status=coverage_status,
                evidence_claim_ids=evidence_claim_ids,
            )
        )

    results_by_requirement = {result.requirement_id: result for result in requirement_results}
    group_results: list[GroupCoverageResult] = []
    for group in payload.groups:
        member_results = [results_by_requirement[item] for item in group.requirement_ids]
        supported_ids = tuple(
            result.requirement_id
            for result in member_results
            if result.status is CoverageStatus.SUPPORTED
        )
        possible_count = sum(
            result.status in {CoverageStatus.SUPPORTED, CoverageStatus.NEEDS_CONFIRMATION}
            for result in member_results
        )
        threshold = (
            len(member_results)
            if group.operator is RequirementGroupOperator.ALL_OF
            else group.minimum_satisfied or 1
        )
        if len(supported_ids) >= threshold:
            group_status = CoverageStatus.SUPPORTED
        elif possible_count >= threshold:
            group_status = CoverageStatus.NEEDS_CONFIRMATION
        else:
            group_status = CoverageStatus.MISSING
        group_results.append(
            GroupCoverageResult(
                group_id=group.id,
                status=group_status,
                supported_requirement_ids=supported_ids,
            )
        )

    grouped_requirement_ids = {
        requirement_id for group in payload.groups for requirement_id in group.requirement_ids
    }
    actionable_gap_ids = [
        result.requirement_id
        for result in requirement_results
        if result.requirement_id not in grouped_requirement_ids
        and result.status is not CoverageStatus.SUPPORTED
    ]
    actionable_gap_ids.extend(
        f"group:{result.group_id}"
        for result in group_results
        if result.status is not CoverageStatus.SUPPORTED
    )

    unit_statuses: list[tuple[CoverageStatus, RequirementPriority]] = [
        (results_by_requirement[requirement.id].status, requirement.priority)
        for requirement in payload.requirements
        if requirement.id not in grouped_requirement_ids
    ]
    unit_statuses.extend(
        (result.status, group.priority)
        for result, group in zip(group_results, payload.groups, strict=True)
    )
    summary = CoverageSummary(
        supported_units=sum(status is CoverageStatus.SUPPORTED for status, _ in unit_statuses),
        needs_confirmation_units=sum(
            status is CoverageStatus.NEEDS_CONFIRMATION for status, _ in unit_statuses
        ),
        missing_units=sum(status is CoverageStatus.MISSING for status, _ in unit_statuses),
        required_missing=sum(
            status is CoverageStatus.MISSING and priority is RequirementPriority.REQUIRED
            for status, priority in unit_statuses
        ),
        preferred_missing=sum(
            status is CoverageStatus.MISSING and priority is RequirementPriority.PREFERRED
            for status, priority in unit_statuses
        ),
    )
    return CoverageEvaluationResponse(
        requirement_results=tuple(requirement_results),
        group_results=tuple(group_results),
        actionable_gap_ids=tuple(actionable_gap_ids),
        summary=summary,
    )
