import base64
import binascii
import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, cast
from uuid import UUID, uuid4

from pydantic import SecretStr, ValidationError

from app.schemas.request_context import (
    MAX_HMAC_SECRET_BYTES,
    MIN_HMAC_SECRET_BYTES,
    REQUEST_ACTION_POLICIES,
    ConsentAttestation,
    ConsentScope,
    RequestAction,
    RequestActionPolicy,
    RequestAuditEvent,
    RequestAuditOutcome,
    RequestContextClaims,
)
from app.services.catalog_persistence import PrincipalKind, TrustedPrincipal

MAX_TOKEN_CHARACTERS = 12_000
MAX_PAYLOAD_BYTES = 8_192
MAX_BOUND_BODY_BYTES = 1_048_576
MAX_TOKEN_LIFETIME_SECONDS = 60
CLOCK_SKEW_SECONDS = 15
CONSENT_MAX_AGE_SECONDS = 600

_BASE64URL_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
_KEY_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?")
_TRUST_DOMAIN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:._-]{2,127}")


class RequestContextError(RuntimeError):
    pass


class RequestContextInvalid(RequestContextError):
    pass


class RequestContextConsentRequired(RequestContextError):
    pass


class RequestContextReplayed(RequestContextError):
    pass


class RequestContextReplayStoreUnavailable(RequestContextError):
    pass


@dataclass(frozen=True, slots=True)
class RequestContextVerificationKey:
    secret: SecretStr
    issuer: str
    audience: str
    allowed_actions: frozenset[str]

    def __post_init__(self) -> None:
        _validated_secret(self.secret)
        if _TRUST_DOMAIN_PATTERN.fullmatch(self.issuer) is None:
            raise ValueError("request-context issuer is invalid")
        if _TRUST_DOMAIN_PATTERN.fullmatch(self.audience) is None:
            raise ValueError("request-context audience is invalid")
        if len(self.allowed_actions) > len(RequestAction):
            raise ValueError("too many request-context actions")
        for action in self.allowed_actions:
            try:
                RequestAction(action)
            except ValueError as exc:
                raise ValueError("request-context action policy is invalid") from exc


class RequestReplayGuard(Protocol):
    async def consume(
        self,
        *,
        issuer: str,
        key_id: str,
        request_id: UUID,
        expires_at: int,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class VerifiedRequestContext:
    principal: TrustedPrincipal
    request_id: UUID
    idempotency_key: UUID
    action: RequestAction
    issuer: str
    audience: str
    key_id: str
    issued_at: int
    expires_at: int
    consents: tuple[ConsentAttestation, ...]

    def require_consent(self, scope: str | ConsentScope) -> ConsentAttestation:
        try:
            expected = scope if isinstance(scope, ConsentScope) else ConsentScope(scope)
        except ValueError as exc:
            raise RequestContextConsentRequired("required consent is missing") from exc
        for item in self.consents:
            if item.scope is expected:
                return item
        raise RequestContextConsentRequired("required consent is missing")


async def verify_request_context(
    token: str,
    *,
    verification_keys: Mapping[str, RequestContextVerificationKey],
    expected_action: str | RequestAction,
    method: str,
    path: str,
    query: str,
    content_type: str,
    content_encoding: str,
    body: bytes,
    replay_guard: RequestReplayGuard,
    now: datetime,
) -> VerifiedRequestContext:
    _validate_runtime_request(body, now)
    payload_segment, signature, payload = _decode_token(token)
    key_id = _untrusted_key_id(payload)
    verification_key = verification_keys.get(key_id)
    if verification_key is None:
        raise RequestContextInvalid("request context is invalid")
    _verify_signature(payload_segment, signature, key_id, verification_key.secret)
    claims = _validate_claims(payload)
    action = _expected_action(expected_action)
    policy = REQUEST_ACTION_POLICIES[action]
    _validate_key_policy(claims, key_id, action, verification_key)
    now_timestamp = int(now.timestamp())
    _validate_time_window(claims, now_timestamp)
    _validate_request_binding(
        claims,
        policy,
        method=method,
        path=path,
        query=query,
        content_type=content_type,
        content_encoding=content_encoding,
        body=body,
    )
    parsed_body = _parse_json_object(body)
    consent = _validate_consent(claims, policy, now_timestamp)
    if action is RequestAction.ANALYSIS_EVALUATE:
        if parsed_body.get("allowRemoteProcessing") is not True:
            raise RequestContextConsentRequired("remote-processing consent is required")
    await _consume_replay(claims, key_id, replay_guard)
    principal = TrustedPrincipal(
        kind=PrincipalKind.AUTHENTICATED_USER,
        subject=claims.sub,
    )
    return VerifiedRequestContext(
        principal=principal,
        request_id=claims.jti,
        idempotency_key=claims.idempotency_key,
        action=claims.action,
        issuer=claims.iss,
        audience=claims.aud,
        key_id=claims.kid,
        issued_at=claims.iat,
        expires_at=claims.exp,
        consents=(consent,),
    )


def build_request_audit_event(
    context: VerifiedRequestContext,
    *,
    outcome: RequestAuditOutcome,
    occurred_at: datetime,
    latency_ms: int,
    audit_secret: SecretStr,
    error_code: str | None = None,
) -> RequestAuditEvent:
    secret = _validated_secret(audit_secret)
    policy = REQUEST_ACTION_POLICIES[context.action]
    consent = context.require_consent(policy.required_consent)
    subject_pseudonym = _pseudonym(
        secret,
        b"gradpath.audit.subject.v1\n",
        context.principal.subject,
    )
    request_identity = f"{context.issuer}\n{context.key_id}\n{context.request_id}"
    request_pseudonym = _pseudonym(
        secret,
        b"gradpath.audit.request.v1\n",
        request_identity,
    )
    return RequestAuditEvent(
        event_id=uuid4(),
        occurred_at=occurred_at,
        action=context.action,
        outcome=outcome,
        principal_kind="authenticated_user",
        subject_pseudonym=subject_pseudonym,
        request_pseudonym=request_pseudonym,
        key_id=context.key_id,
        consent_version=consent.version,
        consent_granted=consent.granted,
        latency_ms=latency_ms,
        error_code=error_code,
    )


def _validate_runtime_request(body: object, now: datetime) -> None:
    if not isinstance(body, bytes) or len(body) > MAX_BOUND_BODY_BYTES:
        raise RequestContextInvalid("request context is invalid")
    if now.tzinfo is None or now.utcoffset() is None:
        raise RequestContextInvalid("request context is invalid")


def _decode_token(token: object) -> tuple[str, bytes, dict[str, object]]:
    if not isinstance(token, str) or not 1 <= len(token) <= MAX_TOKEN_CHARACTERS:
        raise RequestContextInvalid("request context is invalid")
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "v1":
        raise RequestContextInvalid("request context is invalid")
    payload_segment, signature_segment = parts[1], parts[2]
    payload_bytes = _decode_base64url(payload_segment)
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise RequestContextInvalid("request context is invalid")
    signature = _decode_base64url(signature_segment)
    if len(signature) != hashlib.sha256().digest_size:
        raise RequestContextInvalid("request context is invalid")
    return payload_segment, signature, _parse_json_object(payload_bytes)


def _decode_base64url(segment: str) -> bytes:
    if _BASE64URL_PATTERN.fullmatch(segment) is None or len(segment) % 4 == 1:
        raise RequestContextInvalid("request context is invalid")
    padding = "=" * (-len(segment) % 4)
    try:
        decoded = base64.b64decode(
            (segment + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise RequestContextInvalid("request context is invalid") from exc
    if _encode_base64url(decoded) != segment:
        raise RequestContextInvalid("request context is invalid")
    return decoded


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _parse_json_object(value: bytes) -> dict[str, object]:
    try:
        decoded = value.decode("utf-8")
        parsed = cast(
            object,
            json.loads(
                decoded,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_json_constant,
            ),
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        _DuplicateJsonKey,
        RecursionError,
        ValueError,
    ) as exc:
        raise RequestContextInvalid("request context is invalid") from exc
    if not isinstance(parsed, dict):
        raise RequestContextInvalid("request context is invalid")
    return cast(dict[str, object], parsed)


class _DuplicateJsonKey(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(value)


def _untrusted_key_id(payload: dict[str, object]) -> str:
    value = payload.get("kid")
    if not isinstance(value, str) or _KEY_ID_PATTERN.fullmatch(value) is None:
        raise RequestContextInvalid("request context is invalid")
    return value


def _verify_signature(
    payload_segment: str,
    signature: bytes,
    key_id: str,
    secret: SecretStr,
) -> None:
    signing_input = (
        b"gradpath.request-context.v1\n"
        + key_id.encode("ascii")
        + b"\n"
        + payload_segment.encode("ascii")
    )
    expected = hmac.new(_validated_secret(secret), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise RequestContextInvalid("request context is invalid")


def _validate_claims(payload: dict[str, object]) -> RequestContextClaims:
    try:
        return RequestContextClaims.model_validate(payload)
    except ValidationError as exc:
        raise RequestContextInvalid("request context is invalid") from exc


def _expected_action(value: str | RequestAction) -> RequestAction:
    try:
        return value if isinstance(value, RequestAction) else RequestAction(value)
    except ValueError as exc:
        raise RequestContextInvalid("request context is invalid") from exc


def _validate_key_policy(
    claims: RequestContextClaims,
    key_id: str,
    action: RequestAction,
    verification_key: RequestContextVerificationKey,
) -> None:
    if (
        claims.kid != key_id
        or claims.iss != verification_key.issuer
        or claims.aud != verification_key.audience
        or claims.action is not action
        or action.value not in verification_key.allowed_actions
    ):
        raise RequestContextInvalid("request context is invalid")


def _validate_time_window(claims: RequestContextClaims, now_timestamp: int) -> None:
    lifetime = claims.exp - claims.iat
    if (
        lifetime <= 0
        or lifetime > MAX_TOKEN_LIFETIME_SECONDS
        or claims.iat > now_timestamp + CLOCK_SKEW_SECONDS
        or claims.exp <= now_timestamp - CLOCK_SKEW_SECONDS
    ):
        raise RequestContextInvalid("request context is invalid")


def _validate_request_binding(
    claims: RequestContextClaims,
    policy: RequestActionPolicy,
    *,
    method: str,
    path: str,
    query: str,
    content_type: str,
    content_encoding: str,
    body: bytes,
) -> None:
    if (
        claims.method != policy.method
        or claims.path != policy.path
        or claims.query != ""
        or claims.content_type != policy.content_type
        or claims.content_encoding != policy.content_encoding
        or method != claims.method
        or path != claims.path
        or query != claims.query
        or content_type != claims.content_type
        or content_encoding != claims.content_encoding
        or len(body) != claims.body_length
    ):
        raise RequestContextInvalid("request context is invalid")
    observed_hash = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if not hmac.compare_digest(observed_hash, claims.body_sha256):
        raise RequestContextInvalid("request context is invalid")


def _validate_consent(
    claims: RequestContextClaims,
    policy: RequestActionPolicy,
    now_timestamp: int,
) -> ConsentAttestation:
    consent_ids = {item.consent_id for item in claims.consents}
    consent_scopes = {item.scope for item in claims.consents}
    if len(consent_ids) != len(claims.consents) or len(consent_scopes) != len(claims.consents):
        raise RequestContextInvalid("request context is invalid")
    if len(claims.consents) != 1:
        if not claims.consents:
            raise RequestContextConsentRequired("required consent is missing")
        raise RequestContextInvalid("request context is invalid")
    consent = claims.consents[0]
    newest_attestation = min(
        claims.iat + CLOCK_SKEW_SECONDS,
        now_timestamp + CLOCK_SKEW_SECONDS,
    )
    if (
        consent.scope is not policy.required_consent
        or consent.granted is not True
        or consent.processor != policy.consent_processor
        or consent.purpose != policy.consent_purpose
        or consent.version != policy.consent_version
        or consent.policy_sha256 != policy.consent_policy_sha256
        or consent.attested_at < claims.iat - CONSENT_MAX_AGE_SECONDS
        or consent.attested_at > newest_attestation
    ):
        raise RequestContextConsentRequired("required consent is invalid")
    return consent


async def _consume_replay(
    claims: RequestContextClaims,
    key_id: str,
    replay_guard: RequestReplayGuard,
) -> None:
    try:
        accepted = await replay_guard.consume(
            issuer=claims.iss,
            key_id=key_id,
            request_id=claims.jti,
            expires_at=claims.exp + CLOCK_SKEW_SECONDS,
        )
    except Exception as exc:
        raise RequestContextReplayStoreUnavailable("replay store is unavailable") from exc
    if accepted is not True:
        raise RequestContextReplayed("request context was replayed")


def _validated_secret(secret: object) -> bytes:
    if not isinstance(secret, SecretStr):
        raise ValueError("request-context secret is invalid")
    value = secret.get_secret_value()
    encoded = value.encode("utf-8")
    if value != value.strip() or not MIN_HMAC_SECRET_BYTES <= len(encoded) <= MAX_HMAC_SECRET_BYTES:
        raise ValueError("request-context secret is invalid")
    return encoded


def _pseudonym(secret: bytes, domain: bytes, value: str) -> str:
    digest = hmac.new(secret, domain + value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{digest}"
