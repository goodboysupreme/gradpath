import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from app.schemas.job_sources import JobSourceId, PermissionBasis
from app.schemas.provider_postings import (
    ProviderAccountConfig,
    ProviderClassificationReason,
    ProviderClassificationStatus,
    ProviderIssueCode,
    ProviderPayloadErrorCode,
    ProviderPosting,
    ProviderRecordFailureCode,
)
from app.services.provider_postings import (
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


def encode_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def account(provider: JobSourceId) -> ProviderAccountConfig:
    return ProviderAccountConfig(
        provider=provider,
        source_account="example",
        employer_display_name="Configured Example Systems",
        permission_basis=PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
    )


def lever_posting() -> ProviderPosting:
    result = parse_lever_page(
        account(JobSourceId.LEVER),
        fixture_bytes("lever.json"),
        observed_at=OBSERVED_AT,
    )
    return result.postings[0]


@pytest.mark.parametrize(
    "blocked_tag",
    ["template", "noscript", "iframe", "object", "svg", "math"],
)
def test_malformed_blocked_html_cannot_release_hidden_text(blocked_tag: str) -> None:
    payload = fixture_dict("greenhouse.json")
    jobs = cast(list[dict[str, object]], payload["jobs"])
    jobs[0]["content"] = (
        "<p>Build reliable Python services and write focused automated tests.</p>"
        f"<{blocked_tag}></p>HIDDEN-PROMPT-SENTINEL</{blocked_tag}>"
        "<p>Collaborate with engineers on safe production releases.</p>"
    )

    result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    assert len(result.postings) == 1
    assert "HIDDEN-PROMPT-SENTINEL" not in result.postings[0].description


def test_html_void_elements_do_not_count_as_nested_content() -> None:
    payload = fixture_dict("greenhouse.json")
    jobs = cast(list[dict[str, object]], payload["jobs"])
    jobs[0]["content"] = (
        "<p>Build reliable Python services and write focused automated tests.</p>"
        + ("<br>" * 70)
        + "<p>Collaborate with engineers on safe production releases.</p>"
    )

    result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    assert len(result.postings) == 1
    assert result.record_failures == ()


@pytest.mark.parametrize(
    "host",
    ["2130706433", "0x7f000001", "0177.0.0.1", "127.1"],
)
def test_alternate_private_ip_forms_are_rejected_after_url_canonicalization(host: str) -> None:
    payload = fixture_list("lever.json")
    payload[0]["hostedUrl"] = f"https://{host}/private"

    result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    posting = result.postings[0]
    assert posting.public_listing_url is None
    assert ProviderIssueCode.UNSAFE_PUBLIC_LISTING_URL in posting.issues


def test_classification_uses_the_same_unicode_normalized_title_that_students_see() -> None:
    payload = fixture_list("lever.json")
    payload[0]["text"] = "Backend Engineering In\u200btern"
    categories = cast(dict[str, object], payload[0]["categories"])
    categories["commitment"] = "Full-time"

    result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    posting = result.postings[0]
    assert posting.title == "Backend Engineering Intern"
    assert posting.classification.status is ProviderClassificationStatus.NEEDS_REVIEW
    assert (
        posting.classification.reason_code
        is ProviderClassificationReason.EMPLOYMENT_SIGNAL_CONFLICT
    )


def test_invalid_optional_links_warn_without_quarantining_the_posting() -> None:
    payload = fixture_list("lever.json")
    payload[0]["hostedUrl"] = ""
    payload[0]["applyUrl"] = ""

    result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    assert result.record_failures == ()
    posting = result.postings[0]
    assert posting.public_listing_url is None
    assert posting.application_url is None
    assert set(posting.issues) == {
        ProviderIssueCode.UNSAFE_PUBLIC_LISTING_URL,
        ProviderIssueCode.UNSAFE_APPLICATION_URL,
    }


def test_control_characters_in_external_identity_are_quarantined_without_echo() -> None:
    payload = fixture_list("lever.json")
    payload[0]["id"] = "lever-ok\nFORGED-AUDIT-LINE"

    result = parse_lever_page(
        account(JobSourceId.LEVER),
        encode_json(payload),
        observed_at=OBSERVED_AT,
    )

    assert result.postings == ()
    assert result.record_failures[0].reason_code is ProviderRecordFailureCode.INVALID_CRITICAL_FIELD
    assert "FORGED-AUDIT-LINE" not in result.model_dump_json()


def test_duplicate_identity_is_fatal_even_when_duplicate_record_is_otherwise_invalid() -> None:
    payload = fixture_list("lever.json")
    duplicate = deepcopy(payload[0])
    duplicate["text"] = "x"
    payload.append(duplicate)

    with pytest.raises(ProviderPayloadError) as error:
        parse_lever_page(
            account(JobSourceId.LEVER),
            encode_json(payload),
            observed_at=OBSERVED_AT,
        )

    assert error.value.code is ProviderPayloadErrorCode.DUPLICATE_POSTING_ID


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_record_ref", "http://api.lever.co/v0/postings/example/lever-example-1"),
        (
            "provider_record_ref",
            "https://api.lever.co/v0/postings/other/lever-example-1",
        ),
        ("public_listing_url", "https://2130706433/private"),
        ("application_url", "https://user:password@example.org/apply"),
    ],
)
def test_provider_posting_schema_enforces_url_boundary_when_constructed_directly(
    field: str,
    value: str,
) -> None:
    payload = lever_posting().model_dump()
    payload[field] = value

    with pytest.raises(ValidationError):
        ProviderPosting.model_validate(payload)


def test_provider_declared_organization_is_used_for_greenhouse_and_smartrecruiters() -> None:
    greenhouse = fixture_dict("greenhouse.json")
    greenhouse_jobs = cast(list[dict[str, object]], greenhouse["jobs"])
    greenhouse_jobs[0]["company_name"] = "Provider Declared Greenhouse Company"
    greenhouse_result = parse_greenhouse_snapshot(
        account(JobSourceId.GREENHOUSE),
        encode_json(greenhouse),
        observed_at=OBSERVED_AT,
    )
    assert greenhouse_result.postings[0].organization == ("Provider Declared Greenhouse Company")

    smart_list = fixture_dict("smartrecruiters-list.json")
    summaries = cast(list[dict[str, object]], smart_list["content"])
    company = cast(dict[str, object], summaries[0]["company"])
    company["name"] = "Provider Declared Smart Company"
    smart_result = parse_smartrecruiters_page(
        account(JobSourceId.SMARTRECRUITERS),
        encode_json(smart_list),
        {"smart-example-1": fixture_bytes("smartrecruiters-detail.json")},
        observed_at=OBSERVED_AT,
    )
    assert smart_result.postings[0].organization == "Provider Declared Smart Company"


def test_smartrecruiters_ref_must_match_the_server_constructed_record_reference() -> None:
    smart_list = fixture_dict("smartrecruiters-list.json")
    summaries = cast(list[dict[str, object]], smart_list["content"])
    summaries[0]["ref"] = "https://example.org/untrusted-detail"

    result = parse_smartrecruiters_page(
        account(JobSourceId.SMARTRECRUITERS),
        encode_json(smart_list),
        {"smart-example-1": fixture_bytes("smartrecruiters-detail.json")},
        observed_at=OBSERVED_AT,
    )

    assert result.postings == ()
    assert result.record_failures[0].reason_code is ProviderRecordFailureCode.INVALID_CRITICAL_FIELD


def test_ashby_optional_observed_id_does_not_change_canonical_url_snapshot_identity() -> None:
    baseline = fixture_dict("ashby.json")
    baseline_result = parse_ashby_snapshot(
        account(JobSourceId.ASHBY),
        encode_json(baseline),
        observed_at=OBSERVED_AT,
    )

    with_id = deepcopy(baseline)
    jobs = cast(list[dict[str, object]], with_id["jobs"])
    jobs[0]["id"] = "0d38d70f-446d-4f2d-ac45-bc48e3ea1095"
    with_id_result = parse_ashby_snapshot(
        account(JobSourceId.ASHBY),
        encode_json(with_id),
        observed_at=OBSERVED_AT,
    )

    assert baseline_result.postings[0].snapshot_fingerprint == (
        with_id_result.postings[0].snapshot_fingerprint
    )
