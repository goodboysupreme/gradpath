import unicodedata
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from ipaddress import ip_address
from typing import Literal, Self
from urllib.parse import unquote

from pydantic import (
    AnyHttpUrl,
    AwareDatetime,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.schemas.base import CamelContractModel
from app.schemas.domain import AccessLevel, CareerTrack, OpportunityKind


class JobSourceId(StrEnum):
    USER_UPLOAD = "user_upload"
    CAMPUS_AUTHORIZED = "campus_authorized"
    SYNTHETIC_PRACTICE = "synthetic_practice"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    SMARTRECRUITERS = "smartrecruiters"


SOURCE_SCHEMA_VERSIONS = {
    JobSourceId.USER_UPLOAD: "manual-v1",
    JobSourceId.CAMPUS_AUTHORIZED: "campus-import-v1",
    JobSourceId.SYNTHETIC_PRACTICE: "synthetic-v1",
    JobSourceId.GREENHOUSE: "greenhouse-job-board-v1",
    JobSourceId.LEVER: "lever-postings-v0",
    JobSourceId.ASHBY: "ashby-public-posting-v1",
    JobSourceId.SMARTRECRUITERS: "smartrecruiters-posting-v1",
}


class PermissionBasis(StrEnum):
    USER_PROVIDED = "user_provided"
    PLACEMENT_CELL_AUTHORIZED = "placement_cell_authorized"
    INTERNAL_PRACTICE = "internal_practice"
    EMPLOYER_AUTHORIZED = "employer_authorized"
    PUBLIC_API_TERMS_REVIEWED = "public_api_terms_reviewed"


class AcquisitionMethod(StrEnum):
    DIRECT_UPLOAD = "direct_upload"
    AUTHORIZED_EXPORT = "authorized_export"
    PRACTICE_FIXTURE = "practice_fixture"
    OFFICIAL_API = "official_api"


class IntegrationStatus(StrEnum):
    AVAILABLE = "available"
    REQUIRES_AUTHORIZATION = "requires_authorization"
    PLANNED = "planned"


class IdentityStrategy(StrEnum):
    CONTENT_FINGERPRINT = "content_fingerprint"
    EXTERNAL_ID = "external_id"
    CANONICAL_URL = "canonical_url"
    PROVIDER_RECORD_OR_CONTENT = "provider_record_or_content"


class PaginationStrategy(StrEnum):
    NONE = "none"
    FULL_SNAPSHOT = "full_snapshot"
    SKIP_LIMIT = "skip_limit"
    OFFSET_LIMIT = "offset_limit"


class ChangeStrategy(StrEnum):
    CONTENT_HASH = "content_hash"
    UPDATED_AT_AND_CONTENT_HASH = "updated_at_and_content_hash"
    SNAPSHOT_AND_CONTENT_HASH = "snapshot_and_content_hash"
    PUBLISHED_AT_AND_CONTENT_HASH = "published_at_and_content_hash"


class PostingVerification(StrEnum):
    USER_ASSERTED = "user_asserted"
    CAMPUS_AUTHORIZED = "campus_authorized"
    PROVIDER_RECORD = "provider_record"
    SYNTHETIC_PRACTICE = "synthetic_practice"


class CatalogEligibility(StrEnum):
    PRIVATE_ANALYSIS_ONLY = "private_analysis_only"
    CAMPUS_CATALOG = "campus_catalog"
    PUBLIC_CATALOG = "public_catalog"
    PRACTICE_ONLY = "practice_only"


class JobSourceDefinition(CamelContractModel):
    id: JobSourceId
    label: str
    acquisition_method: AcquisitionMethod
    integration_status: IntegrationStatus
    identity_strategy: IdentityStrategy
    pagination_strategy: PaginationStrategy
    change_strategy: ChangeStrategy
    official_documentation: str | None
    requires_permission_basis: bool


class JobSourcePolicy(CamelContractModel):
    authenticated_scraping_allowed: Literal[False] = False
    token_discovery_allowed: Literal[False] = False
    permission_basis_required: Literal[True] = True
    provenance_required: Literal[True] = True
    synthetic_may_appear_as_live: Literal[False] = False


class JobSourceRegistryResponse(CamelContractModel):
    sources: tuple[JobSourceDefinition, ...]
    policy: JobSourcePolicy


OFFICIAL_SOURCE_IDS = frozenset(
    {
        JobSourceId.GREENHOUSE,
        JobSourceId.LEVER,
        JobSourceId.ASHBY,
        JobSourceId.SMARTRECRUITERS,
    }
)
PRIVILEGED_SOURCE_IDS = OFFICIAL_SOURCE_IDS | {
    JobSourceId.CAMPUS_AUTHORIZED,
    JobSourceId.SYNTHETIC_PRACTICE,
}
PROVIDER_HOSTS = {
    JobSourceId.GREENHOUSE: frozenset({"boards.greenhouse.io", "job-boards.greenhouse.io"}),
    JobSourceId.LEVER: frozenset({"jobs.lever.co", "jobs.eu.lever.co"}),
    JobSourceId.ASHBY: frozenset({"jobs.ashbyhq.com"}),
    JobSourceId.SMARTRECRUITERS: frozenset({"jobs.smartrecruiters.com"}),
}


def normalize_human_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


class JobDescriptionNormalizationRequest(CamelContractModel):
    source_id: JobSourceId
    permission_basis: PermissionBasis
    source_account: str | None = Field(default=None, min_length=2, max_length=200)
    external_id: str | None = Field(default=None, min_length=1, max_length=300)
    source_url: AnyHttpUrl | None = None
    schema_version: str | None = Field(default=None, min_length=2, max_length=100)
    observed_at: AwareDatetime
    authorization_ref: SecretStr | None = None
    organization: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=50, max_length=250_000)
    location: str | None = Field(default=None, min_length=2, max_length=200)
    tracks: tuple[CareerTrack, ...] = Field(min_length=1, max_length=4)
    opportunity_kind: OpportunityKind
    application_url: AnyHttpUrl | None = None
    published_at: AwareDatetime | None = None
    application_deadline: AwareDatetime | None = None

    @field_validator(
        "source_account",
        "external_id",
        "schema_version",
        "organization",
        "title",
        "description",
        "location",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> object:
        return normalize_human_text(value) if isinstance(value, str) else value

    @field_validator("source_url", "application_url")
    @classmethod
    def require_safe_https_url(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        if (
            value.scheme != "https"
            or value.username is not None
            or value.password is not None
            or value.fragment is not None
            or value.port not in {None, 443}
        ):
            raise ValueError("URL must be a canonical HTTPS URL")
        host = value.host
        if host is None:
            raise ValueError("URL host is required")
        normalized_host = host.casefold().rstrip(".").strip("[]")
        if normalized_host == "localhost" or normalized_host.endswith(
            (".localhost", ".local", ".internal", ".home.arpa")
        ):
            raise ValueError("Local URLs are not accepted")
        try:
            address = ip_address(normalized_host)
        except ValueError:
            pass
        else:
            if not address.is_global:
                raise ValueError("Private or reserved IP URLs are not accepted")
        return value

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if len(set(self.tracks)) != len(self.tracks):
            raise ValueError("tracks must be unique")
        if self.opportunity_kind is OpportunityKind.STATION_PROJECT:
            if self.tracks != (CareerTrack.PS2,):
                raise ValueError("station projects require the PS-II track")
        elif self.opportunity_kind is OpportunityKind.INTERNSHIP:
            if not set(self.tracks) <= {CareerTrack.SI, CareerTrack.OFF_CAMPUS}:
                raise ValueError("internships require SI or off-campus tracks")
        elif not set(self.tracks) <= {CareerTrack.PLACEMENT, CareerTrack.OFF_CAMPUS}:
            raise ValueError("jobs require placement or off-campus tracks")

        if self.published_at is not None and self.published_at > self.observed_at:
            raise ValueError("publication cannot be later than observation")
        if (
            self.published_at is not None
            and self.application_deadline is not None
            and self.application_deadline < self.published_at
        ):
            raise ValueError("application deadline cannot precede publication")
        if self.observed_at > datetime.now(UTC) + timedelta(days=1):
            raise ValueError("observation time is implausibly far in the future")

        reference = (
            self.authorization_ref.get_secret_value().strip()
            if self.authorization_ref is not None
            else None
        )
        if reference is not None and not 3 <= len(reference) <= 500:
            raise ValueError("authorization evidence is invalid")

        if self.source_id is JobSourceId.USER_UPLOAD:
            self._validate_user_upload(reference)
        elif self.source_id is JobSourceId.CAMPUS_AUTHORIZED:
            self._validate_campus_import(reference)
        elif self.source_id is JobSourceId.SYNTHETIC_PRACTICE:
            self._validate_synthetic_record(reference)
        else:
            self._validate_provider_record(reference)
        return self

    def _validate_user_upload(self, reference: str | None) -> None:
        if self.permission_basis is not PermissionBasis.USER_PROVIDED:
            raise ValueError("user uploads require user-provided provenance")
        if any(
            value is not None
            for value in (
                self.source_account,
                self.external_id,
                self.source_url,
                self.schema_version,
                reference,
            )
        ):
            raise ValueError("user uploads cannot claim external provenance")

    def _validate_campus_import(self, reference: str | None) -> None:
        if self.permission_basis is not PermissionBasis.PLACEMENT_CELL_AUTHORIZED:
            raise ValueError("campus imports require placement-cell authorization")
        if self.source_account is None or self.external_id is None or reference is None:
            raise ValueError("campus import provenance is incomplete")
        if self.schema_version not in {
            None,
            SOURCE_SCHEMA_VERSIONS[JobSourceId.CAMPUS_AUTHORIZED],
        }:
            raise ValueError("campus import schema version is unsupported")

    def _validate_synthetic_record(self, reference: str | None) -> None:
        if self.permission_basis is not PermissionBasis.INTERNAL_PRACTICE:
            raise ValueError("practice records require internal provenance")
        if (
            self.source_account is None
            or self.external_id is None
            or self.schema_version != SOURCE_SCHEMA_VERSIONS[JobSourceId.SYNTHETIC_PRACTICE]
        ):
            raise ValueError("practice record provenance is incomplete")
        if any(
            value is not None
            for value in (
                self.source_url,
                self.application_url,
                self.published_at,
                self.application_deadline,
                reference,
            )
        ):
            raise ValueError("practice records cannot contain live-listing metadata")

    def _validate_provider_record(self, reference: str | None) -> None:
        if self.permission_basis not in {
            PermissionBasis.EMPLOYER_AUTHORIZED,
            PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
        }:
            raise ValueError("provider record permission basis is invalid")
        if (
            self.source_account is None
            or self.source_url is None
            or self.schema_version != SOURCE_SCHEMA_VERSIONS[self.source_id]
        ):
            raise ValueError("provider record provenance is incomplete")
        if self.source_id is not JobSourceId.ASHBY and self.external_id is None:
            raise ValueError("provider record external identity is missing")
        if reference is not None:
            raise ValueError("provider records cannot contain campus authorization evidence")
        host = self.source_url.host
        if host is None or host.casefold() not in PROVIDER_HOSTS[self.source_id]:
            raise ValueError("source URL does not match the provider")
        if self.source_id is JobSourceId.ASHBY:
            self._validate_ashby_locator()

    def _validate_ashby_locator(self) -> None:
        if self.source_account is None or self.source_url is None:
            raise ValueError("Ashby source identity is incomplete")
        segments = tuple(
            normalize_human_text(unquote(segment))
            for segment in (self.source_url.path or "").split("/")
            if segment
        )
        if (
            len(segments) < 2
            or segments[0].casefold() != self.source_account.casefold()
            or any(segment in {".", ".."} for segment in segments)
        ):
            raise ValueError("Ashby source URL must identify a posting for its account")


class NormalizedJobSource(CamelContractModel):
    source_id: JobSourceId
    permission_basis: PermissionBasis
    access_level: AccessLevel
    source_account: str | None
    external_id: str | None
    source_url: AnyHttpUrl | None
    schema_version: str
    observed_at: AwareDatetime
    verification: PostingVerification
    catalog_eligibility: CatalogEligibility
    source_locator_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class NormalizedJobDescriptionResponse(CamelContractModel):
    source: NormalizedJobSource
    organization: str
    title: str
    description: str
    location: str | None
    tracks: tuple[CareerTrack, ...]
    opportunity_kind: OpportunityKind
    application_url: AnyHttpUrl | None
    published_at: AwareDatetime | None
    application_deadline: AwareDatetime | None
    content_fingerprint: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fingerprint_version: Literal["jd-normalized-v1"] = "jd-normalized-v1"
