import unicodedata
from enum import StrEnum
from ipaddress import ip_address
from typing import Annotated, Self
from urllib.parse import quote, unquote, urlsplit

from pydantic import AnyHttpUrl, AwareDatetime, Field, field_validator, model_validator

from app.schemas.base import ContractModel
from app.schemas.domain import CareerTrack, OpportunityKind
from app.schemas.job_sources import OFFICIAL_SOURCE_IDS, JobSourceId, PermissionBasis


class ProviderRegion(StrEnum):
    GLOBAL = "global"
    EU = "eu"


class ProviderClassificationStatus(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class ProviderClassificationReason(StrEnum):
    EMPLOYMENT_SIGNAL_MISSING = "employment_signal_missing"
    EMPLOYMENT_SIGNAL_UNSUPPORTED = "employment_signal_unsupported"
    EMPLOYMENT_SIGNAL_CONFLICT = "employment_signal_conflict"
    POSTING_UNLISTED = "posting_unlisted"
    POSTING_INACTIVE = "posting_inactive"


class ProviderIssueCode(StrEnum):
    UNSAFE_PUBLIC_LISTING_URL = "unsafe_public_listing_url"
    UNSAFE_APPLICATION_URL = "unsafe_application_url"


class ProviderPayloadErrorCode(StrEnum):
    PAYLOAD_TOO_LARGE = "payload_too_large"
    INVALID_JSON = "invalid_json"
    DUPLICATE_JSON_KEY = "duplicate_json_key"
    STRUCTURE_LIMIT_EXCEEDED = "structure_limit_exceeded"
    INVALID_ENVELOPE = "invalid_envelope"
    UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
    DUPLICATE_POSTING_ID = "duplicate_posting_id"
    DETAIL_MISSING = "detail_missing"
    DETAIL_ID_MISMATCH = "detail_id_mismatch"


class ProviderRecordFailureCode(StrEnum):
    INVALID_CRITICAL_FIELD = "invalid_critical_field"
    INVALID_IDENTITY_URL = "invalid_identity_url"


Sha256Fingerprint = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
BoundedHttpUrl = Annotated[AnyHttpUrl, Field(max_length=4_096)]
SourceAccount = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
    ),
]

_REVIEW_REASONS = frozenset(
    {
        ProviderClassificationReason.EMPLOYMENT_SIGNAL_MISSING,
        ProviderClassificationReason.EMPLOYMENT_SIGNAL_UNSUPPORTED,
        ProviderClassificationReason.EMPLOYMENT_SIGNAL_CONFLICT,
    }
)
_REJECTION_REASONS = frozenset(
    {
        ProviderClassificationReason.POSTING_UNLISTED,
        ProviderClassificationReason.POSTING_INACTIVE,
    }
)
_LEVER_API_HOSTS = frozenset({"api.lever.co", "api.eu.lever.co"})
_LOCAL_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
_MAX_URL_DECODE_PASSES = 16


def _contains_forbidden_control(value: str) -> bool:
    return any(unicodedata.category(character).startswith("C") for character in value)


def _require_safe_decoded_url_text(value: str) -> None:
    decoded = value
    for _ in range(_MAX_URL_DECODE_PASSES):
        candidate = unquote(decoded)
        if candidate == decoded:
            return
        if "\\" in candidate or _contains_forbidden_control(candidate):
            raise ValueError("URL contains unsafe encoded characters")
        decoded = candidate
    raise ValueError("URL encoding nesting exceeds the safety limit")


def _require_safe_raw_url(value: object) -> object:
    if not isinstance(value, (str, AnyHttpUrl)):
        raise ValueError("URL must be text")
    text = str(value)
    if (
        len(text) > 4_096
        or text != text.strip()
        or "\\" in text
        or "#" in text
        or any(character.isspace() for character in text)
        or _contains_forbidden_control(text)
    ):
        raise ValueError("URL is unsafe")
    _require_safe_decoded_url_text(text)

    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError:
        raise ValueError("URL is malformed") from None
    if (
        parsed.scheme.casefold() != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port not in {None, 443}
    ):
        raise ValueError("URL must be safe HTTPS")
    return value


def _normalized_safe_host(value: AnyHttpUrl) -> str:
    host = value.host
    if host is None:
        raise ValueError("URL host is required")
    try:
        normalized = host.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError:
        raise ValueError("URL host is invalid") from None
    if normalized == "localhost" or normalized.endswith(_LOCAL_HOST_SUFFIXES):
        raise ValueError("local URL hosts are forbidden")
    try:
        address = ip_address(normalized.strip("[]"))
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("non-global URL hosts are forbidden")
    return normalized


def require_safe_https_url(value: AnyHttpUrl) -> AnyHttpUrl:
    text = str(value)
    if (
        value.scheme.casefold() != "https"
        or value.username is not None
        or value.password is not None
        or value.fragment is not None
        or value.port not in {None, 443}
        or "\\" in text
        or _contains_forbidden_control(text)
    ):
        raise ValueError("URL must be safe HTTPS")
    _require_safe_decoded_url_text(text)
    _normalized_safe_host(value)
    return value


def _canonical_path_component(value: str) -> str:
    return quote(value, safe="-._~")


class ProviderAccountConfig(ContractModel):
    provider: JobSourceId
    source_account: SourceAccount
    employer_display_name: str = Field(min_length=2, max_length=200)
    permission_basis: PermissionBasis
    lever_region: ProviderRegion | None = None

    @model_validator(mode="after")
    def validate_provider_account(self) -> Self:
        if self.provider not in OFFICIAL_SOURCE_IDS:
            raise ValueError("provider must be an official public source")
        if self.permission_basis not in {
            PermissionBasis.EMPLOYER_AUTHORIZED,
            PermissionBasis.PUBLIC_API_TERMS_REVIEWED,
        }:
            raise ValueError("provider permission basis is invalid")
        if self.provider is not JobSourceId.LEVER and self.lever_region is not None:
            raise ValueError("lever_region is only valid for Lever accounts")
        return self


class ProviderEmploymentSignal(ContractModel):
    field: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$",
    )
    value: str = Field(min_length=1, max_length=200)


class ProviderClassification(ContractModel):
    status: ProviderClassificationStatus
    tracks: tuple[CareerTrack, ...] = Field(max_length=1)
    opportunity_kind: OpportunityKind | None = None
    reason_code: ProviderClassificationReason | None = None

    @model_validator(mode="after")
    def validate_classification(self) -> Self:
        if self.status is ProviderClassificationStatus.ACCEPTED:
            if self.tracks != (CareerTrack.OFF_CAMPUS,):
                raise ValueError("accepted provider postings must be off-campus")
            if self.opportunity_kind not in {
                OpportunityKind.INTERNSHIP,
                OpportunityKind.JOB,
            }:
                raise ValueError("accepted provider postings must be internships or jobs")
            if self.reason_code is not None:
                raise ValueError("accepted provider postings cannot have a reason code")
            return self

        if self.tracks or self.opportunity_kind is not None:
            raise ValueError("unaccepted provider postings cannot have catalog classification")
        if self.reason_code is None:
            raise ValueError("unaccepted provider postings require a reason code")
        if (
            self.status is ProviderClassificationStatus.NEEDS_REVIEW
            and self.reason_code not in _REVIEW_REASONS
        ):
            raise ValueError("review classification reason is invalid")
        if (
            self.status is ProviderClassificationStatus.REJECTED
            and self.reason_code not in _REJECTION_REASONS
        ):
            raise ValueError("rejection classification reason is invalid")
        return self


class ProviderPosting(ContractModel):
    provider: JobSourceId
    source_account: SourceAccount
    organization: str = Field(min_length=2, max_length=200)
    external_id: str | None = Field(default=None, min_length=1, max_length=300)
    provider_record_ref: BoundedHttpUrl
    public_listing_url: BoundedHttpUrl | None = None
    application_url: BoundedHttpUrl | None = None
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=1, max_length=250_000)
    location: str | None = Field(default=None, min_length=2, max_length=200)
    published_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    application_deadline: AwareDatetime | None = None
    employment_signal: ProviderEmploymentSignal | None = None
    classification: ProviderClassification
    issues: tuple[ProviderIssueCode, ...] = Field(default=(), max_length=16)
    schema_version: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$",
    )
    adapter_version: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9][a-z0-9._-]{1,99}$",
    )
    observed_at: AwareDatetime
    snapshot_fingerprint: Sha256Fingerprint

    @field_validator(
        "provider_record_ref",
        "public_listing_url",
        "application_url",
        mode="before",
    )
    @classmethod
    def require_safe_raw_urls(cls, value: object) -> object:
        if value is None:
            return None
        return _require_safe_raw_url(value)

    @field_validator("provider_record_ref", "public_listing_url", "application_url")
    @classmethod
    def require_safe_canonical_urls(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        return require_safe_https_url(value)

    @field_validator("external_id", mode="before")
    @classmethod
    def require_unambiguous_external_id(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("external ID must be text")
        if (
            value != value.strip()
            or any(character.isspace() for character in value)
            or _contains_forbidden_control(value)
        ):
            raise ValueError("external ID contains ambiguous characters")
        return value

    @field_validator("issues")
    @classmethod
    def require_unique_issues(
        cls,
        value: tuple[ProviderIssueCode, ...],
    ) -> tuple[ProviderIssueCode, ...]:
        if len(set(value)) != len(value):
            raise ValueError("issues must be unique")
        return value

    @model_validator(mode="after")
    def validate_posting(self) -> Self:
        if self.provider not in OFFICIAL_SOURCE_IDS:
            raise ValueError("posting provider must be an official public source")
        self._validate_provider_record_ref()
        if self.published_at is not None and self.published_at > self.observed_at:
            raise ValueError("publication cannot be later than observation")
        if self.updated_at is not None and self.updated_at > self.observed_at:
            raise ValueError("update cannot be later than observation")
        if (
            self.published_at is not None
            and self.application_deadline is not None
            and self.application_deadline < self.published_at
        ):
            raise ValueError("application deadline cannot precede publication")
        return self

    def _validate_provider_record_ref(self) -> None:
        reference = self.provider_record_ref
        host = reference.host
        if host is None or host != _normalized_safe_host(reference) or "?" in str(reference):
            raise ValueError("provider record reference is not canonical")

        account = _canonical_path_component(self.source_account)
        external_id = self.external_id
        path = reference.path or ""
        if self.provider is JobSourceId.GREENHOUSE:
            if external_id is None:
                raise ValueError("Greenhouse records require an external ID")
            expected_path = f"/v1/boards/{account}/jobs/{_canonical_path_component(external_id)}"
            if host != "boards-api.greenhouse.io" or path != expected_path:
                raise ValueError("Greenhouse record reference is invalid")
            return

        if self.provider is JobSourceId.LEVER:
            if external_id is None:
                raise ValueError("Lever records require an external ID")
            expected_path = f"/v0/postings/{account}/{_canonical_path_component(external_id)}"
            if host not in _LEVER_API_HOSTS or path != expected_path:
                raise ValueError("Lever record reference is invalid")
            return

        if self.provider is JobSourceId.SMARTRECRUITERS:
            if external_id is None:
                raise ValueError("SmartRecruiters records require an external ID")
            expected_path = (
                f"/v1/companies/{account}/postings/{_canonical_path_component(external_id)}"
            )
            if host != "api.smartrecruiters.com" or path != expected_path:
                raise ValueError("SmartRecruiters record reference is invalid")
            return

        if self.provider is not JobSourceId.ASHBY:
            raise ValueError("posting provider is unsupported")
        segments = path.split("/")
        if (
            host != "jobs.ashbyhq.com"
            or len(segments) != 3
            or segments[0] != ""
            or segments[1] != account
            or not segments[2]
            or _canonical_path_component(unquote(segments[2])) != segments[2]
            or self.public_listing_url is None
            or str(self.public_listing_url) != str(reference)
        ):
            raise ValueError("Ashby record reference is invalid")


class ProviderRecordFailure(ContractModel):
    record_index: int = Field(strict=True, ge=0, le=9_999)
    reason_code: ProviderRecordFailureCode
    snapshot_fingerprint: Sha256Fingerprint


class ParsedProviderBatch(ContractModel):
    provider: JobSourceId
    source_account: SourceAccount
    provider_total: int | None = Field(default=None, strict=True, ge=0, le=10_000_000)
    records_seen: int = Field(strict=True, ge=0, le=10_000)
    postings: tuple[ProviderPosting, ...] = Field(max_length=10_000)
    record_failures: tuple[ProviderRecordFailure, ...] = Field(max_length=10_000)

    @model_validator(mode="after")
    def validate_batch(self) -> Self:
        if self.provider not in OFFICIAL_SOURCE_IDS:
            raise ValueError("batch provider must be an official public source")
        if self.records_seen != len(self.postings) + len(self.record_failures):
            raise ValueError("records_seen must reconcile with parsed records")
        if self.provider_total is not None and self.provider_total < self.records_seen:
            raise ValueError("provider_total cannot be smaller than records_seen")
        if any(
            posting.provider is not self.provider or posting.source_account != self.source_account
            for posting in self.postings
        ):
            raise ValueError("posting provenance must match its batch")
        record_refs = tuple(str(posting.provider_record_ref) for posting in self.postings)
        if len(set(record_refs)) != len(record_refs):
            raise ValueError("posting record references must be unique")
        failure_indexes = tuple(failure.record_index for failure in self.record_failures)
        if len(set(failure_indexes)) != len(failure_indexes):
            raise ValueError("record failure indexes must be unique")
        if any(index >= self.records_seen for index in failure_indexes):
            raise ValueError("record failure index is outside the batch")
        return self


__all__ = [
    "ParsedProviderBatch",
    "ProviderAccountConfig",
    "ProviderClassification",
    "ProviderClassificationReason",
    "ProviderClassificationStatus",
    "ProviderEmploymentSignal",
    "ProviderIssueCode",
    "ProviderPayloadErrorCode",
    "ProviderPosting",
    "ProviderRecordFailure",
    "ProviderRecordFailureCode",
    "ProviderRegion",
    "require_safe_https_url",
]
