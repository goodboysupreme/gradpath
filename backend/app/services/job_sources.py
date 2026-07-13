import hashlib
import json
from collections.abc import Mapping
from urllib.parse import quote, unquote

from pydantic import AnyHttpUrl

from app.schemas.domain import AccessLevel
from app.schemas.job_sources import (
    SOURCE_SCHEMA_VERSIONS,
    AcquisitionMethod,
    CatalogEligibility,
    ChangeStrategy,
    IdentityStrategy,
    IntegrationStatus,
    JobDescriptionNormalizationRequest,
    JobSourceDefinition,
    JobSourceId,
    JobSourcePolicy,
    JobSourceRegistryResponse,
    NormalizedJobDescriptionResponse,
    NormalizedJobSource,
    PaginationStrategy,
    PostingVerification,
    normalize_human_text,
)

FINGERPRINT_VERSION = "jd-normalized-v1"
MAX_NORMALIZATION_BODY_BYTES = 1_048_576

SOURCE_DEFINITIONS = (
    JobSourceDefinition(
        id=JobSourceId.USER_UPLOAD,
        label="User-provided JD",
        acquisition_method=AcquisitionMethod.DIRECT_UPLOAD,
        integration_status=IntegrationStatus.AVAILABLE,
        identity_strategy=IdentityStrategy.CONTENT_FINGERPRINT,
        pagination_strategy=PaginationStrategy.NONE,
        change_strategy=ChangeStrategy.CONTENT_HASH,
        official_documentation=None,
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.CAMPUS_AUTHORIZED,
        label="Authorized campus import",
        acquisition_method=AcquisitionMethod.AUTHORIZED_EXPORT,
        integration_status=IntegrationStatus.REQUIRES_AUTHORIZATION,
        identity_strategy=IdentityStrategy.EXTERNAL_ID,
        pagination_strategy=PaginationStrategy.NONE,
        change_strategy=ChangeStrategy.CONTENT_HASH,
        official_documentation=None,
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.SYNTHETIC_PRACTICE,
        label="Synthetic practice JD",
        acquisition_method=AcquisitionMethod.PRACTICE_FIXTURE,
        integration_status=IntegrationStatus.AVAILABLE,
        identity_strategy=IdentityStrategy.EXTERNAL_ID,
        pagination_strategy=PaginationStrategy.NONE,
        change_strategy=ChangeStrategy.CONTENT_HASH,
        official_documentation=None,
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.GREENHOUSE,
        label="Greenhouse Job Board API",
        acquisition_method=AcquisitionMethod.OFFICIAL_API,
        integration_status=IntegrationStatus.PLANNED,
        identity_strategy=IdentityStrategy.EXTERNAL_ID,
        pagination_strategy=PaginationStrategy.FULL_SNAPSHOT,
        change_strategy=ChangeStrategy.UPDATED_AT_AND_CONTENT_HASH,
        official_documentation="https://developers.greenhouse.io/job-board.html",
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.LEVER,
        label="Lever Postings API",
        acquisition_method=AcquisitionMethod.OFFICIAL_API,
        integration_status=IntegrationStatus.PLANNED,
        identity_strategy=IdentityStrategy.EXTERNAL_ID,
        pagination_strategy=PaginationStrategy.SKIP_LIMIT,
        change_strategy=ChangeStrategy.SNAPSHOT_AND_CONTENT_HASH,
        official_documentation="https://github.com/lever/postings-api",
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.ASHBY,
        label="Ashby Public Job Posting API",
        acquisition_method=AcquisitionMethod.OFFICIAL_API,
        integration_status=IntegrationStatus.PLANNED,
        identity_strategy=IdentityStrategy.CANONICAL_URL,
        pagination_strategy=PaginationStrategy.FULL_SNAPSHOT,
        change_strategy=ChangeStrategy.PUBLISHED_AT_AND_CONTENT_HASH,
        official_documentation=("https://developers.ashbyhq.com/docs/public-job-posting-api"),
        requires_permission_basis=True,
    ),
    JobSourceDefinition(
        id=JobSourceId.SMARTRECRUITERS,
        label="SmartRecruiters Posting API",
        acquisition_method=AcquisitionMethod.OFFICIAL_API,
        integration_status=IntegrationStatus.PLANNED,
        identity_strategy=IdentityStrategy.EXTERNAL_ID,
        pagination_strategy=PaginationStrategy.OFFSET_LIMIT,
        change_strategy=ChangeStrategy.SNAPSHOT_AND_CONTENT_HASH,
        official_documentation=("https://developers.smartrecruiters.com/docs/customer-overview"),
        requires_permission_basis=True,
    ),
)

SOURCE_RESULTS = {
    JobSourceId.USER_UPLOAD: (
        AccessLevel.USER_PRIVATE,
        PostingVerification.USER_ASSERTED,
        CatalogEligibility.PRIVATE_ANALYSIS_ONLY,
    ),
    JobSourceId.CAMPUS_AUTHORIZED: (
        AccessLevel.CAMPUS_RESTRICTED,
        PostingVerification.CAMPUS_AUTHORIZED,
        CatalogEligibility.CAMPUS_CATALOG,
    ),
    JobSourceId.SYNTHETIC_PRACTICE: (
        AccessLevel.PUBLIC,
        PostingVerification.SYNTHETIC_PRACTICE,
        CatalogEligibility.PRACTICE_ONLY,
    ),
    JobSourceId.GREENHOUSE: (
        AccessLevel.PUBLIC,
        PostingVerification.PROVIDER_RECORD,
        CatalogEligibility.PUBLIC_CATALOG,
    ),
    JobSourceId.LEVER: (
        AccessLevel.PUBLIC,
        PostingVerification.PROVIDER_RECORD,
        CatalogEligibility.PUBLIC_CATALOG,
    ),
    JobSourceId.ASHBY: (
        AccessLevel.PUBLIC,
        PostingVerification.PROVIDER_RECORD,
        CatalogEligibility.PUBLIC_CATALOG,
    ),
    JobSourceId.SMARTRECRUITERS: (
        AccessLevel.PUBLIC,
        PostingVerification.PROVIDER_RECORD,
        CatalogEligibility.PUBLIC_CATALOG,
    ),
}


def job_source_registry() -> JobSourceRegistryResponse:
    return JobSourceRegistryResponse(
        sources=SOURCE_DEFINITIONS,
        policy=JobSourcePolicy(),
    )


def normalize_job_description(
    payload: JobDescriptionNormalizationRequest,
) -> NormalizedJobDescriptionResponse:
    content_fingerprint = _fingerprint(
        "gradpath.jd.content",
        {
            "description": payload.description.casefold(),
            "location": payload.location.casefold() if payload.location is not None else None,
            "opportunityKind": payload.opportunity_kind.value,
            "organization": payload.organization.casefold(),
            "title": payload.title.casefold(),
            "tracks": sorted(track.value for track in payload.tracks),
            "version": FINGERPRINT_VERSION,
        },
    )
    access_level, verification, eligibility = SOURCE_RESULTS[payload.source_id]
    source_locator_fingerprint = _source_locator_fingerprint(
        payload,
        content_fingerprint,
    )
    return NormalizedJobDescriptionResponse(
        source=NormalizedJobSource(
            source_id=payload.source_id,
            permission_basis=payload.permission_basis,
            access_level=access_level,
            source_account=payload.source_account,
            external_id=payload.external_id,
            source_url=payload.source_url,
            schema_version=SOURCE_SCHEMA_VERSIONS[payload.source_id],
            observed_at=payload.observed_at,
            verification=verification,
            catalog_eligibility=eligibility,
            source_locator_fingerprint=source_locator_fingerprint,
        ),
        organization=payload.organization,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        tracks=payload.tracks,
        opportunity_kind=payload.opportunity_kind,
        application_url=payload.application_url,
        published_at=payload.published_at,
        application_deadline=payload.application_deadline,
        content_fingerprint=content_fingerprint,
    )


def _source_locator_fingerprint(
    payload: JobDescriptionNormalizationRequest,
    content_fingerprint: str,
) -> str:
    if payload.source_id is JobSourceId.USER_UPLOAD:
        return content_fingerprint
    identity: dict[str, str] = {
        "sourceAccount": (payload.source_account or "").casefold(),
        "sourceId": payload.source_id.value,
    }
    if payload.source_id is JobSourceId.ASHBY:
        identity["canonicalUrl"] = _canonical_url(payload.source_url)
    else:
        identity["externalId"] = payload.external_id or ""
    return _fingerprint("gradpath.jd.source-locator", identity)


def _canonical_url(value: AnyHttpUrl | None) -> str:
    if value is None or value.host is None:
        raise ValueError("canonical source URL is required")
    segments = [
        normalize_human_text(unquote(segment))
        for segment in (value.path or "").split("/")
        if segment
    ]
    if segments:
        segments[0] = segments[0].casefold()
    path = "/" + "/".join(quote(segment, safe="-._~") for segment in segments)
    return f"https://{value.host.casefold()}{path}"


def _fingerprint(domain: str, payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        {"domain": domain, "payload": payload},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
