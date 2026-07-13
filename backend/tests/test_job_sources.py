import re
from copy import deepcopy
from typing import Any

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.main import create_app

INTERNAL_TOKEN = "test-internal-token-that-is-long-enough"
SOURCE_INGESTION_TOKEN = "test-source-ingestion-token-that-is-long-enough"


def valid_user_upload() -> dict[str, Any]:
    return {
        "sourceId": "user_upload",
        "permissionBasis": "user_provided",
        "observedAt": "2026-07-13T12:00:00+05:30",
        "organization": "Acme Labs",
        "title": "Software Engineering Intern",
        "description": (
            "Build reliable Python services, design APIs, write tests, and collaborate with "
            "engineers on production-quality internship projects."
        ),
        "location": "Bengaluru, India",
        "tracks": ["si"],
        "opportunityKind": "internship",
    }


def post_normalization(
    payload: dict[str, Any],
    *,
    include_token: bool = True,
    include_source_token: bool = False,
    configure_source_token: bool = True,
) -> httpx.Response:
    headers = {"X-GradPath-Internal-Token": INTERNAL_TOKEN} if include_token else {}
    if include_source_token:
        headers["X-GradPath-Source-Ingestion-Token"] = SOURCE_INGESTION_TOKEN
    source_token = SecretStr(SOURCE_INGESTION_TOKEN) if configure_source_token else None
    settings = Settings.model_validate(
        {
            "internal_api_token": SecretStr(INTERNAL_TOKEN),
            "source_ingestion_token": source_token,
        }
    )
    with TestClient(create_app(settings=settings)) as client:
        return client.post(
            "/api/v1/job-descriptions/normalize",
            json=payload,
            headers=headers,
        )


def test_job_source_registry_is_permission_first_and_explicitly_not_a_scraper() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/job-sources")

    assert response.status_code == 200
    result = response.json()
    assert [source["id"] for source in result["sources"]] == [
        "user_upload",
        "campus_authorized",
        "synthetic_practice",
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
    ]
    assert result["policy"] == {
        "authenticatedScrapingAllowed": False,
        "tokenDiscoveryAllowed": False,
        "permissionBasisRequired": True,
        "provenanceRequired": True,
        "syntheticMayAppearAsLive": False,
    }
    by_id = {source["id"]: source for source in result["sources"]}
    assert by_id["user_upload"]["integrationStatus"] == "available"
    assert by_id["campus_authorized"]["integrationStatus"] == "requires_authorization"
    assert by_id["greenhouse"] == {
        "id": "greenhouse",
        "label": "Greenhouse Job Board API",
        "acquisitionMethod": "official_api",
        "integrationStatus": "planned",
        "identityStrategy": "external_id",
        "paginationStrategy": "full_snapshot",
        "changeStrategy": "updated_at_and_content_hash",
        "officialDocumentation": "https://developers.greenhouse.io/job-board.html",
        "requiresPermissionBasis": True,
    }
    assert by_id["ashby"]["identityStrategy"] == "canonical_url"
    assert by_id["lever"]["paginationStrategy"] == "skip_limit"
    assert by_id["smartrecruiters"]["paginationStrategy"] == "offset_limit"


def test_normalization_requires_internal_authentication() -> None:
    response = post_normalization(valid_user_upload(), include_token=False)

    assert response.status_code == 401


def test_source_ingestion_credential_must_be_distinct_from_internal_token() -> None:
    shared_token = SecretStr("shared-token-that-is-long-enough-to-be-rejected")

    with pytest.raises(ValidationError):
        Settings(
            internal_api_token=shared_token,
            source_ingestion_token=shared_token,
        )


def test_user_uploaded_jd_is_private_user_asserted_and_not_public_catalog_content() -> None:
    response = post_normalization(valid_user_upload())

    assert response.status_code == 200
    result = response.json()
    assert set(result) == {
        "source",
        "organization",
        "title",
        "description",
        "location",
        "tracks",
        "opportunityKind",
        "applicationUrl",
        "publishedAt",
        "applicationDeadline",
        "contentFingerprint",
        "fingerprintVersion",
    }
    assert result["source"] == {
        "sourceId": "user_upload",
        "permissionBasis": "user_provided",
        "accessLevel": "user_private",
        "sourceAccount": None,
        "externalId": None,
        "sourceUrl": None,
        "schemaVersion": "manual-v1",
        "observedAt": "2026-07-13T12:00:00+05:30",
        "verification": "user_asserted",
        "catalogEligibility": "private_analysis_only",
        "sourceLocatorFingerprint": result["contentFingerprint"],
    }
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", result["contentFingerprint"])
    assert result["fingerprintVersion"] == "jd-normalized-v1"
    assert response.headers["Cache-Control"] == "no-store"


def test_content_fingerprint_is_stable_across_cosmetic_whitespace_and_case() -> None:
    first = valid_user_upload()
    second = deepcopy(first)
    second["organization"] = "  ａｃｍｅ   ｌａｂｓ  "
    second["title"] = " software   engineering INTERN "
    first["tracks"] = ["si", "off_campus"]
    second["tracks"] = ["off_campus", "si"]
    second["description"] = (
        "Build reliable Python services, design APIs, write tests,\n\n"
        "and collaborate with engineers on production-quality internship projects."
    )

    first_result = post_normalization(first).json()
    second_result = post_normalization(second).json()

    assert first_result["contentFingerprint"] == second_result["contentFingerprint"]
    assert second_result["organization"] == "acme labs"
    assert second_result["title"] == "software engineering INTERN"


def test_material_description_change_changes_content_fingerprint() -> None:
    first = valid_user_upload()
    second = deepcopy(first)
    second["description"] += " Experience with Kubernetes is required."

    first_result = post_normalization(first).json()
    second_result = post_normalization(second).json()

    assert first_result["contentFingerprint"] != second_result["contentFingerprint"]


def test_material_target_fields_change_content_fingerprint() -> None:
    baseline = valid_user_upload()
    baseline_fingerprint = post_normalization(baseline).json()["contentFingerprint"]
    variants = (
        {"organization": "Different Labs"},
        {"title": "Platform Engineering Intern"},
        {"location": "Hyderabad, India"},
        {"tracks": ["off_campus"]},
        {"tracks": ["placement"], "opportunityKind": "job"},
    )

    for changes in variants:
        changed = deepcopy(baseline)
        changed.update(changes)
        assert post_normalization(changed).json()["contentFingerprint"] != baseline_fingerprint


def test_user_upload_cannot_be_promoted_to_public_catalog_by_the_caller() -> None:
    payload = valid_user_upload()
    payload["accessLevel"] = "public"

    response = post_normalization(payload)

    assert response.status_code == 422


def test_campus_import_requires_restricted_scope_and_authorization_reference() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "campus_authorized",
            "permissionBasis": "placement_cell_authorized",
            "sourceAccount": "bits-pilani-si-2026",
            "externalId": "SI-2026-0042",
        }
    )

    missing_reference = post_normalization(payload, include_source_token=True)
    assert missing_reference.status_code == 422

    payload["authorizationRef"] = "placement-cell-import-2026-01"
    unprivileged = post_normalization(payload)
    assert unprivileged.status_code == 403

    response = post_normalization(payload, include_source_token=True)

    assert response.status_code == 200
    assert response.json()["source"]["verification"] == "campus_authorized"
    assert response.json()["source"]["catalogEligibility"] == "campus_catalog"
    assert "authorizationRef" not in response.text


def test_privileged_source_ingestion_fails_closed_when_credential_is_unconfigured() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "campus_authorized",
            "permissionBasis": "placement_cell_authorized",
            "sourceAccount": "bits-pilani-si-2026",
            "externalId": "SI-2026-0042",
            "authorizationRef": "placement-cell-import-2026-01",
        }
    )

    response = post_normalization(
        payload,
        include_source_token=True,
        configure_source_token=False,
    )

    assert response.status_code == 503


def test_validation_errors_do_not_echo_authorization_evidence() -> None:
    secret_reference = "placement-cell-secret-sentinel-8472"
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "campus_authorized",
            "permissionBasis": "placement_cell_authorized",
            "sourceAccount": "bits-pilani-si-2026",
            "externalId": "SI-2026-0042",
            "authorizationRef": secret_reference,
            "inventedTrustFlag": True,
        }
    )

    response = post_normalization(payload, include_source_token=True)

    assert response.status_code == 422
    assert "authorizationRef" not in response.text
    assert secret_reference not in response.text


def test_official_provider_record_requires_complete_provenance_and_permission() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "greenhouse",
            "permissionBasis": "public_api_terms_reviewed",
            "sourceAccount": "acme-board",
            "schemaVersion": "greenhouse-job-board-v1",
        }
    )

    assert post_normalization(payload, include_source_token=True).status_code == 422

    payload.update(
        {
            "externalId": "1234567",
            "sourceUrl": "https://boards.greenhouse.io/acme/jobs/1234567",
            "applicationUrl": "https://boards.greenhouse.io/acme/jobs/1234567",
        }
    )
    response = post_normalization(payload, include_source_token=True)

    assert response.status_code == 200
    source = response.json()["source"]
    assert source["verification"] == "provider_record"
    assert source["catalogEligibility"] == "public_catalog"
    assert source["sourceLocatorFingerprint"] != response.json()["contentFingerprint"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", source["sourceLocatorFingerprint"])

    changed_identity = deepcopy(payload)
    changed_identity["externalId"] = "7654321"
    changed_response = post_normalization(
        changed_identity,
        include_source_token=True,
    )
    assert (
        changed_response.json()["source"]["sourceLocatorFingerprint"]
        != source["sourceLocatorFingerprint"]
    )

    unsupported_schema = deepcopy(payload)
    unsupported_schema["schemaVersion"] = "anything-v999"
    assert (
        post_normalization(
            unsupported_schema,
            include_source_token=True,
        ).status_code
        == 422
    )


def test_official_provider_urls_are_https_and_bound_to_the_provider() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "greenhouse",
            "permissionBasis": "public_api_terms_reviewed",
            "sourceAccount": "acme-board",
            "externalId": "1234567",
            "schemaVersion": "greenhouse-job-board-v1",
            "sourceUrl": "http://boards.greenhouse.io/acme/jobs/1234567",
            "applicationUrl": "https://boards.greenhouse.io/acme/jobs/1234567",
        }
    )

    assert post_normalization(payload, include_source_token=True).status_code == 422

    payload["sourceUrl"] = "https://example.com/acme/jobs/1234567"
    assert post_normalization(payload, include_source_token=True).status_code == 422

    payload["sourceUrl"] = "https://boards.greenhouse.io/acme/jobs/1234567"
    payload["applicationUrl"] = "http://example.com/apply"
    assert post_normalization(payload, include_source_token=True).status_code == 422

    payload["applicationUrl"] = "https://127.0.0.1/admin"
    assert post_normalization(payload, include_source_token=True).status_code == 422


def test_ashby_uses_canonical_url_identity_without_inventing_an_external_id() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "ashby",
            "permissionBasis": "employer_authorized",
            "sourceAccount": "acme",
            "sourceUrl": "https://jobs.ashbyhq.com/acme/example-job",
            "applicationUrl": "https://jobs.ashbyhq.com/acme/example-job/application",
            "schemaVersion": "ashby-public-posting-v1",
        }
    )

    root_url = deepcopy(payload)
    root_url["sourceUrl"] = "https://jobs.ashbyhq.com"
    assert post_normalization(root_url, include_source_token=True).status_code == 422

    wrong_account = deepcopy(payload)
    wrong_account["sourceUrl"] = "https://jobs.ashbyhq.com/other/example-job"
    assert post_normalization(wrong_account, include_source_token=True).status_code == 422

    response = post_normalization(payload, include_source_token=True)

    assert response.status_code == 200
    assert response.json()["source"]["externalId"] is None
    assert response.json()["source"]["verification"] == "provider_record"

    second_posting = deepcopy(payload)
    second_posting["sourceUrl"] = "https://jobs.ashbyhq.com/acme/second-job"
    second_response = post_normalization(second_posting, include_source_token=True)
    assert second_response.status_code == 200
    assert (
        second_response.json()["source"]["sourceLocatorFingerprint"]
        != response.json()["source"]["sourceLocatorFingerprint"]
    )


def test_synthetic_practice_jd_can_never_masquerade_as_a_live_listing() -> None:
    payload = valid_user_upload()
    payload.update(
        {
            "sourceId": "synthetic_practice",
            "permissionBasis": "internal_practice",
            "sourceAccount": "gradpath-samples-v1",
            "externalId": "sde-intern-sample",
            "schemaVersion": "synthetic-v1",
        }
    )

    response = post_normalization(payload, include_source_token=True)

    assert response.status_code == 200
    assert response.json()["source"]["verification"] == "synthetic_practice"
    assert response.json()["source"]["catalogEligibility"] == "practice_only"

    payload["applicationUrl"] = "https://example.com/not-a-real-job"
    assert post_normalization(payload, include_source_token=True).status_code == 422


def test_ps2_station_project_requires_ps2_track_and_unique_tracks() -> None:
    payload = valid_user_upload()
    payload["opportunityKind"] = "station_project"

    assert post_normalization(payload).status_code == 422

    payload["tracks"] = ["ps2", "ps2"]
    assert post_normalization(payload).status_code == 422

    payload["tracks"] = ["ps2"]
    assert post_normalization(payload).status_code == 200

    payload = valid_user_upload()
    payload["opportunityKind"] = "job"
    assert post_normalization(payload).status_code == 422

    payload["tracks"] = ["off_campus"]
    assert post_normalization(payload).status_code == 200


def test_job_source_timestamps_are_aware_and_chronologically_valid() -> None:
    payload = valid_user_upload()
    payload["observedAt"] = "2026-07-13T12:00:00"
    assert post_normalization(payload).status_code == 422

    payload["observedAt"] = "2026-07-13T12:00:00+05:30"
    payload["publishedAt"] = "2026-07-14T12:00:00+05:30"
    assert post_normalization(payload).status_code == 422

    payload["publishedAt"] = "2026-07-12T12:00:00+05:30"
    payload["applicationDeadline"] = "2026-07-11T12:00:00+05:30"
    assert post_normalization(payload).status_code == 422


def test_normalization_rejects_oversized_json_before_whitespace_normalization() -> None:
    payload = valid_user_upload()
    payload["description"] += " " * 1_100_000

    response = post_normalization(payload)

    assert response.status_code == 413
    assert response.headers["Cache-Control"] == "no-store"


def test_validation_sanitization_does_not_change_other_endpoint_contracts() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/coverage/evaluate", json={})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_normalization_rejects_unknown_fields() -> None:
    payload = valid_user_upload()
    payload["inventedTrustFlag"] = True

    assert post_normalization(payload).status_code == 422
