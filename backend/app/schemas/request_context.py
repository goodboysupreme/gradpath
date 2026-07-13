from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import (
    UUID4,
    AwareDatetime,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from app.schemas.base import CamelContractModel

REMOTE_PROCESSING_POLICY_SHA256: Final = (
    "sha256:7000cf54e5bb46c5732e660d40fa687339ffee19073f32b75e4693fd6b743a73"
)
PRIVATE_STORAGE_POLICY_SHA256: Final = (
    "sha256:fdde570f26e640b376885d9999ee956c6c6c395d02401acf1f23512089c5e7fa"
)
REMOTE_PROCESSING_CONSENT_VERSION: Final = "remote-ai-v1"
PRIVATE_STORAGE_CONSENT_VERSION: Final = "private-storage-v1"
MAX_SIGNED_BODY_BYTES: Final = 1_048_576
MIN_HMAC_SECRET_BYTES: Final = 32
MAX_HMAC_SECRET_BYTES: Final = 1_024

BoundedEpoch = Annotated[int, Field(strict=True, ge=0, le=9_223_372_036_854_775_807)]
CanonicalDigest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
PseudonymDigest = Annotated[str, Field(pattern=r"^hmac-sha256:[0-9a-f]{64}$")]
KeyId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?$",
    ),
]


class _StrictCamelContractModel(CamelContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)


class RequestAction(StrEnum):
    ANALYSIS_EVALUATE = "analysis.evaluate"
    CATALOG_PERSIST_PRIVATE = "catalog.persist.private"


class ConsentScope(StrEnum):
    REMOTE_PROCESSING = "remote_processing"
    PRIVATE_JD_STORAGE = "private_jd_storage"


class RequestAuditOutcome(StrEnum):
    AUTHORIZED = "authorized"
    DENIED = "denied"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class RequestActionPolicy:
    method: str
    path: str
    query: str
    content_type: str
    content_encoding: str
    required_consent: ConsentScope
    consent_processor: str | None
    consent_purpose: str
    consent_version: str
    consent_policy_sha256: str


REQUEST_ACTION_POLICIES: Final[Mapping[RequestAction, RequestActionPolicy]] = MappingProxyType(
    {
        RequestAction.ANALYSIS_EVALUATE: RequestActionPolicy(
            method="POST",
            path="/api/v1/analyses/evaluate",
            query="",
            content_type="application/json",
            content_encoding="identity",
            required_consent=ConsentScope.REMOTE_PROCESSING,
            consent_processor="openrouter",
            consent_purpose="resume_jd_readiness_analysis",
            consent_version=REMOTE_PROCESSING_CONSENT_VERSION,
            consent_policy_sha256=REMOTE_PROCESSING_POLICY_SHA256,
        ),
        RequestAction.CATALOG_PERSIST_PRIVATE: RequestActionPolicy(
            method="POST",
            path="/api/v1/job-descriptions/private",
            query="",
            content_type="application/json",
            content_encoding="identity",
            required_consent=ConsentScope.PRIVATE_JD_STORAGE,
            consent_processor=None,
            consent_purpose="private_jd_storage",
            consent_version=PRIVATE_STORAGE_CONSENT_VERSION,
            consent_policy_sha256=PRIVATE_STORAGE_POLICY_SHA256,
        ),
    }
)


def _canonical_uuid4(value: object) -> object:
    if not isinstance(value, str):
        raise ValueError("identifier must be a canonical UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("identifier must be a canonical UUID string") from error
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("identifier must be a canonical UUID4 string")
    return value


class ConsentAttestation(_StrictCamelContractModel):
    consent_id: UUID4
    scope: ConsentScope
    granted: StrictBool
    processor: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    purpose: str = Field(
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    version: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )
    policy_sha256: CanonicalDigest
    attested_at: BoundedEpoch

    @field_validator("consent_id", mode="before")
    @classmethod
    def canonical_consent_id(cls, value: object) -> object:
        return _canonical_uuid4(value)


class RequestContextClaims(_StrictCamelContractModel):
    v: Annotated[int, Field(strict=True, ge=1, le=1)]
    iss: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._:-]*$",
    )
    aud: str = Field(
        min_length=3,
        max_length=128,
        pattern=r"^[a-z0-9][a-z0-9._:-]*$",
    )
    kid: KeyId
    jti: UUID4
    iat: BoundedEpoch
    exp: BoundedEpoch
    sub: str = Field(min_length=43, max_length=43, pattern=r"^authjs:[0-9a-f-]{36}$")
    principal_kind: Literal["authenticated_user"]
    action: RequestAction
    method: Literal["POST"]
    path: str = Field(min_length=2, max_length=160, pattern=r"^/[a-z0-9./-]+$")
    query: Literal[""]
    content_type: Literal["application/json"]
    content_encoding: Literal["identity"]
    body_length: Annotated[int, Field(strict=True, ge=2, le=MAX_SIGNED_BODY_BYTES)]
    body_sha256: CanonicalDigest
    idempotency_key: UUID4
    consents: tuple[ConsentAttestation, ...] = Field(default=(), max_length=4)

    @field_validator("jti", "idempotency_key", mode="before")
    @classmethod
    def canonical_request_ids(cls, value: object) -> object:
        return _canonical_uuid4(value)

    @field_validator("sub")
    @classmethod
    def canonical_subject(cls, value: str) -> str:
        subject_id = value.removeprefix("authjs:")
        try:
            parsed = UUID(subject_id)
        except ValueError as error:
            raise ValueError("subject must contain a canonical UUID4") from error
        if parsed.version != 4 or str(parsed) != subject_id:
            raise ValueError("subject must contain a canonical UUID4")
        return value

    @model_validator(mode="after")
    def action_binding_is_exact(self) -> Self:
        policy = REQUEST_ACTION_POLICIES[self.action]
        observed = (
            self.method,
            self.path,
            self.query,
            self.content_type,
            self.content_encoding,
        )
        expected = (
            policy.method,
            policy.path,
            policy.query,
            policy.content_type,
            policy.content_encoding,
        )
        if observed != expected:
            raise ValueError("request action transport binding is invalid")
        return self


class RequestAuditEvent(_StrictCamelContractModel):
    event_id: UUID4
    occurred_at: AwareDatetime
    action: RequestAction
    outcome: RequestAuditOutcome
    principal_kind: Literal["authenticated_user"]
    subject_pseudonym: PseudonymDigest
    request_pseudonym: PseudonymDigest
    key_id: KeyId
    consent_version: str | None = Field(default=None, min_length=2, max_length=80)
    consent_granted: StrictBool
    latency_ms: Annotated[int, Field(strict=True, ge=0, le=86_400_000)]
    error_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9._-]*$",
    )

    @field_validator("event_id", mode="before")
    @classmethod
    def canonical_event_id(cls, value: object) -> object:
        if isinstance(value, UUID):
            if value.version != 4:
                raise ValueError("event identifier must be UUID4")
            return value
        return _canonical_uuid4(value)
