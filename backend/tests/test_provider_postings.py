import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.schemas.domain import CareerTrack, OpportunityKind
from app.schemas.job_sources import JobSourceId, PermissionBasis
from app.schemas.provider_postings import (
    ProviderAccountConfig,
    ProviderClassificationReason,
    ProviderClassificationStatus,
    ProviderIssueCode,
    ProviderPayloadErrorCode,
    ProviderRecordFailureCode,
    ProviderRegion,
)
from app.services.provider_postings import (
    MAX_PROVIDER_PAYLOAD_BYTES,
    ProviderPayloadError,
    parse_ashby_snapshot,
    parse_greenhouse_snapshot,
    parse_lever_page,
    parse_smartrecruiters_page,
)

FIXTURES = Path(__file__).parent / "fixtures" / "provider_postings"
OBSERVED_AT = datetime(2026, 7, 13, 12, tzinfo=UTC)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_dict(name: str) -> dict[str, object]:
    value = json.loads(fixture_bytes(name))
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def fixture_list(name: str) -> list[dict[str, object]]:
    value = json.loads(fixture_bytes(name))
    assert isinstance(value, list)
    items = cast(list[object], value)
    assert all(isinstance(item, dict) for item in items)
    return cast(list[dict[str, object]], items)


def encode_json(value: object, *, sort_keys: bool = False) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=sort_keys,
    ).encode("utf-8")


def account(
    provider: JobSourceId,
    *,
    lever_region: ProviderRegion | None = None,
) -> ProviderAccountConfig:
    return ProviderAccountConfig(
        provider=provider,
        source_account="example",
        employer_display_name="Example Systems",
        permission_basis=PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
        lever_region=lever_region,
    )


def assert_payload_error(
    error: pytest.ExceptionInfo[ProviderPayloadError],
    code: ProviderPayloadErrorCode,
) -> None:
    assert error.value.code is code
    assert str(error.value) == code.value


def test_provider_account_config_accepts_only_official_sources_and_server_derived_hosts() -> None:
    config = account(JobSourceId.LEVER, lever_region=ProviderRegion.EU)

    assert config.provider is JobSourceId.LEVER
    assert config.lever_region is ProviderRegion.EU
    assert "fetch_url" not in type(config).model_fields

    with pytest.raises(ValidationError):
        account(JobSourceId.USER_UPLOAD)

    with pytest.raises(ValidationError):
        account(JobSourceId.ASHBY, lever_region=ProviderRegion.EU)


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (
            b'{"jobs":[],"meta":{"total":0},"extra":{"key":1,"key":2}}',
            ProviderPayloadErrorCode.DUPLICATE_JSON_KEY,
        ),
        (
            b'{"jobs":[],"meta":{"total":0},"extra":NaN}',
            ProviderPayloadErrorCode.INVALID_JSON,
        ),
        (
            b'{"jobs":[],"meta":{"total":0},"extra":"\\ud800"}',
            ProviderPayloadErrorCode.INVALID_JSON,
        ),
        (b"\xff", ProviderPayloadErrorCode.INVALID_JSON),
    ],
)
def test_provider_json_boundary_rejects_ambiguous_or_invalid_json(
    payload: bytes,
    expected_code: ProviderPayloadErrorCode,
) -> None:
    with pytest.raises(ProviderPayloadError) as error:
        parse_greenhouse_snapshot(
            account(JobSourceId.GREENHOUSE),
            payload,
            observed_at=OBSERVED_AT,
        )

    assert_payload_error(error, expected_code)


def test_provider_json_boundary_rejects_excessive_size_and_depth() -> None:
    with pytest.raises(ProviderPayloadError) as oversized:
        parse_greenhouse_snapshot(
            account(JobSourceId.GREENHOUSE),
            b" " * (MAX_PROVIDER_PAYLOAD_BYTES + 1),
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(oversized, ProviderPayloadErrorCode.PAYLOAD_TOO_LARGE)

    nested = (
        b'{"jobs":[],"meta":{"total":0},"extra":' + (b'{"value":' * 33) + b"0" + (b"}" * 33) + b"}"
    )
    with pytest.raises(ProviderPayloadError) as excessive_depth:
        parse_greenhouse_snapshot(
            account(JobSourceId.GREENHOUSE),
            nested,
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(
        excessive_depth,
        ProviderPayloadErrorCode.STRUCTURE_LIMIT_EXCEEDED,
    )


def test_greenhouse_snapshot_sanitizes_html_and_never_infers_from_title() -> None:
    result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        fixture_bytes("greenhouse.json"),
        observed_at=OBSERVED_AT,
    )

    assert result.provider is JobSourceId.GREENHOUSE
    assert result.provider_total == 1
    assert result.records_seen == 1
    assert result.record_failures == ()
    posting = result.postings[0]
    assert posting.external_id == "7982460"
    assert str(posting.provider_record_ref) == (
        "https://boards-api.greenhouse.io/v1/boards/example/jobs/7982460"
    )
    assert str(posting.public_listing_url) == (
        "https://careers.example.org/roles/software-engineering-intern"
    )
    assert posting.application_url is None
    assert posting.organization == "Example Systems"
    assert posting.location == "Bengaluru, India"
    assert "Build reliable Python services & APIs" in posting.description
    assert "Write focused tests for every change" in posting.description
    assert "secret" not in posting.description
    assert "tracker.invalid" not in posting.description
    assert posting.published_at == datetime(2026, 7, 1, 8, tzinfo=UTC)
    assert posting.updated_at == datetime(2026, 7, 12, 9, 30, tzinfo=UTC)
    assert posting.application_deadline == datetime(2026, 8, 15, 23, 59, tzinfo=UTC)
    assert posting.employment_signal is None
    assert posting.classification.status is ProviderClassificationStatus.NEEDS_REVIEW
    assert (
        posting.classification.reason_code is ProviderClassificationReason.EMPLOYMENT_SIGNAL_MISSING
    )
    assert posting.classification.tracks == ()
    assert posting.classification.opportunity_kind is None


def test_greenhouse_allows_safe_employer_link_but_never_uses_it_as_provider_ref() -> None:
    payload = fixture_dict("greenhouse.json")
    jobs = cast(list[dict[str, object]], payload["jobs"])
    jobs[0]["absolute_url"] = "https://127.0.0.1/private"

    result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    posting = result.postings[0]
    assert posting.public_listing_url is None
    assert ProviderIssueCode.UNSAFE_PUBLIC_LISTING_URL in posting.issues
    assert str(posting.provider_record_ref).startswith("https://boards-api.greenhouse.io/")


def test_greenhouse_invalid_record_is_bounded_and_total_mismatch_fails_run() -> None:
    payload = fixture_dict("greenhouse.json")
    jobs = cast(list[dict[str, object]], payload["jobs"])
    jobs[0]["id"] = "7982460"
    jobs[0]["content"] = "do-not-echo-critical-record-sentinel"

    result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    assert result.postings == ()
    assert len(result.record_failures) == 1
    assert result.record_failures[0].reason_code is ProviderRecordFailureCode.INVALID_CRITICAL_FIELD
    assert "do-not-echo" not in result.model_dump_json()

    meta = cast(dict[str, object], payload["meta"])
    meta["total"] = 2
    with pytest.raises(ProviderPayloadError) as error:
        parse_greenhouse_snapshot(
            account(JobSourceId.GREENHOUSE),
            encode_json(payload),
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(error, ProviderPayloadErrorCode.INVALID_ENVELOPE)


def test_lever_maps_explicit_internship_and_assembles_description_once() -> None:
    result = parse_lever_page(
        account(JobSourceId.LEVER),
        fixture_bytes("lever.json"),
        observed_at=OBSERVED_AT,
    )

    assert result.provider is JobSourceId.LEVER
    assert result.provider_total is None
    posting = result.postings[0]
    assert posting.classification.status is ProviderClassificationStatus.ACCEPTED
    assert posting.classification.tracks == (CareerTrack.OFF_CAMPUS,)
    assert posting.classification.opportunity_kind is OpportunityKind.INTERNSHIP
    assert posting.employment_signal is not None
    assert posting.employment_signal.field == "categories.commitment"
    assert posting.employment_signal.value == "Internship"
    assert posting.description.split("\n\n") == [
        "Join a small platform team building reliable student-facing services.",
        "Build typed Python APIs and improve production observability.",
        "What you will do",
        "Design bounded ingestion contracts.\nWrite focused parser tests.",
        "You will receive weekly engineering mentorship and code review.",
    ]
    assert "aggregate fallback" not in posting.description
    assert posting.published_at is None
    assert posting.updated_at is None
    assert posting.application_deadline is None


def test_lever_hash_is_semantic_and_documented_changes_are_detected() -> None:
    baseline = fixture_list("lever.json")
    additive = deepcopy(baseline)
    additive[0]["futureProviderField"] = {"ignored": True}

    baseline_result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(baseline),
        observed_at=OBSERVED_AT,
    )
    reordered_result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(additive, sort_keys=True),
        observed_at=OBSERVED_AT + timedelta(hours=1),
    )

    assert (
        baseline_result.postings[0].snapshot_fingerprint
        == reordered_result.postings[0].snapshot_fingerprint
    )

    changed = deepcopy(baseline)
    changed[0]["applyUrl"] = "https://jobs.lever.co/example/lever-example-1/alternate"
    changed_result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(changed),
        observed_at=OBSERVED_AT,
    )
    assert (
        baseline_result.postings[0].snapshot_fingerprint
        != changed_result.postings[0].snapshot_fingerprint
    )
    assert baseline_result.postings[0].description == changed_result.postings[0].description


@pytest.mark.parametrize(
    ("commitment", "expected_reason"),
    [
        ("Full-time", ProviderClassificationReason.EMPLOYMENT_SIGNAL_CONFLICT),
        ("Seasonal Fellowship", ProviderClassificationReason.EMPLOYMENT_SIGNAL_UNSUPPORTED),
    ],
)
def test_lever_does_not_silently_accept_conflicting_or_unknown_signals(
    commitment: str,
    expected_reason: ProviderClassificationReason,
) -> None:
    payload = fixture_list("lever.json")
    categories = cast(dict[str, object], payload[0]["categories"])
    categories["commitment"] = commitment

    result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    classification = result.postings[0].classification
    assert classification.status is ProviderClassificationStatus.NEEDS_REVIEW
    assert classification.reason_code is expected_reason
    assert classification.tracks == ()
    assert classification.opportunity_kind is None


def test_lever_duplicate_ids_fail_the_page_without_leaking_records() -> None:
    payload = fixture_list("lever.json")
    payload.append(deepcopy(payload[0]))
    payload[1]["descriptionBodyPlain"] = "sensitive-duplicate-record-sentinel"

    with pytest.raises(ProviderPayloadError) as error:
        parse_lever_page(
            account(JobSourceId.LEVER),
            encode_json(payload),
            observed_at=OBSERVED_AT,
        )

    assert_payload_error(error, ProviderPayloadErrorCode.DUPLICATE_POSTING_ID)
    assert "sensitive-duplicate" not in str(error.value)


def test_ashby_uses_canonical_url_identity_and_suppresses_unlisted_postings() -> None:
    result = parse_ashby_snapshot(
        account(JobSourceId.ASHBY),
        fixture_bytes("ashby.json"),
        observed_at=OBSERVED_AT,
    )

    assert result.provider is JobSourceId.ASHBY
    assert result.provider_total == 2
    accepted, unlisted = result.postings
    assert accepted.external_id is None
    assert str(accepted.public_listing_url) == (
        "https://jobs.ashbyhq.com/example/data-engineering-intern"
    )
    assert accepted.classification.status is ProviderClassificationStatus.ACCEPTED
    assert accepted.classification.tracks == (CareerTrack.OFF_CAMPUS,)
    assert accepted.classification.opportunity_kind is OpportunityKind.INTERNSHIP
    assert accepted.published_at == datetime(2026, 7, 2, 10, tzinfo=UTC)
    assert accepted.updated_at is None
    assert accepted.application_deadline is None

    assert unlisted.classification.status is ProviderClassificationStatus.REJECTED
    assert unlisted.classification.reason_code is ProviderClassificationReason.POSTING_UNLISTED
    assert unlisted.classification.tracks == ()
    assert unlisted.classification.opportunity_kind is None


def test_ashby_rejects_unsupported_schema_and_quarantines_invalid_identity() -> None:
    payload = fixture_dict("ashby.json")
    payload["apiVersion"] = "2"

    with pytest.raises(ProviderPayloadError) as version_error:
        parse_ashby_snapshot(
            account(JobSourceId.ASHBY),
            encode_json(payload),
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(
        version_error,
        ProviderPayloadErrorCode.UNSUPPORTED_SCHEMA_VERSION,
    )

    payload["apiVersion"] = "1"
    jobs = cast(list[dict[str, object]], payload["jobs"])
    jobs[0]["jobUrl"] = "https://jobs.ashbyhq.com/other/not-this-account"
    result = parse_ashby_snapshot(
        account(JobSourceId.ASHBY),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )
    assert len(result.postings) == 1
    assert len(result.record_failures) == 1
    assert result.record_failures[0].reason_code is ProviderRecordFailureCode.INVALID_IDENTITY_URL


def test_smartrecruiters_combines_list_and_detail_without_inventing_listing_url() -> None:
    detail = fixture_bytes("smartrecruiters-detail.json")
    result = parse_smartrecruiters_page(
        account(JobSourceId.SMARTRECRUITERS),
        fixture_bytes("smartrecruiters-list.json"),
        {"smart-example-1": detail},
        observed_at=OBSERVED_AT,
    )

    assert result.provider is JobSourceId.SMARTRECRUITERS
    assert result.provider_total == 1
    posting = result.postings[0]
    assert posting.external_id == "smart-example-1"
    assert str(posting.provider_record_ref) == (
        "https://api.smartrecruiters.com/v1/companies/example/postings/smart-example-1"
    )
    assert posting.public_listing_url is None
    assert str(posting.application_url) == (
        "https://www.smartrecruiters.com/ExampleSystems/platform-engineer"
    )
    assert posting.organization == "Example Systems"
    assert posting.location == "Bengaluru, Karnataka, India"
    assert posting.classification.status is ProviderClassificationStatus.ACCEPTED
    assert posting.classification.tracks == (CareerTrack.OFF_CAMPUS,)
    assert posting.classification.opportunity_kind is OpportunityKind.JOB
    assert posting.description.split("\n\n") == [
        "Company Description\n"
        "Example Systems builds dependable tools for students and universities.",
        "Job Description\nDesign typed APIs and operate reliable platform services.",
        "Qualifications\nStrong Python fundamentals.\nExperience writing automated tests.",
        "Additional Information\nHybrid work with structured mentorship and regular code review.",
    ]
    assert "doNotLeak" not in posting.description


def test_smartrecruiters_inactive_posting_is_rejected() -> None:
    detail = fixture_dict("smartrecruiters-detail.json")
    detail["active"] = False

    result = parse_smartrecruiters_page(
        account(JobSourceId.SMARTRECRUITERS),
        fixture_bytes("smartrecruiters-list.json"),
        {"smart-example-1": encode_json(detail)},
        observed_at=OBSERVED_AT,
    )

    classification = result.postings[0].classification
    assert classification.status is ProviderClassificationStatus.REJECTED
    assert classification.reason_code is ProviderClassificationReason.POSTING_INACTIVE
    assert classification.tracks == ()


def test_smartrecruiters_requires_every_detail_and_matching_identity() -> None:
    with pytest.raises(ProviderPayloadError) as missing:
        parse_smartrecruiters_page(
            account(JobSourceId.SMARTRECRUITERS),
            fixture_bytes("smartrecruiters-list.json"),
            {},
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(missing, ProviderPayloadErrorCode.DETAIL_MISSING)

    detail = fixture_dict("smartrecruiters-detail.json")
    detail["id"] = "different-posting"
    with pytest.raises(ProviderPayloadError) as mismatch:
        parse_smartrecruiters_page(
            account(JobSourceId.SMARTRECRUITERS),
            fixture_bytes("smartrecruiters-list.json"),
            {"smart-example-1": encode_json(detail)},
            observed_at=OBSERVED_AT,
        )
    assert_payload_error(mismatch, ProviderPayloadErrorCode.DETAIL_ID_MISMATCH)


def test_provider_postings_never_emit_campus_tracks() -> None:
    batches = (
        parse_greenhouse_snapshot(
            account(JobSourceId.GREENHOUSE),
            fixture_bytes("greenhouse.json"),
            observed_at=OBSERVED_AT,
        ),
        parse_lever_page(
            account(JobSourceId.LEVER),
            fixture_bytes("lever.json"),
            observed_at=OBSERVED_AT,
        ),
        parse_ashby_snapshot(
            account(JobSourceId.ASHBY),
            fixture_bytes("ashby.json"),
            observed_at=OBSERVED_AT,
        ),
        parse_smartrecruiters_page(
            account(JobSourceId.SMARTRECRUITERS),
            fixture_bytes("smartrecruiters-list.json"),
            {"smart-example-1": fixture_bytes("smartrecruiters-detail.json")},
            observed_at=OBSERVED_AT,
        ),
    )

    for batch in batches:
        for posting in batch.postings:
            assert set(posting.classification.tracks) <= {CareerTrack.OFF_CAMPUS}
