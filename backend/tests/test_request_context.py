import base64
import hashlib
import hmac
import importlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from anyio import run
from pydantic import SecretStr, ValidationError

from app.config import Settings

NOW = 1_783_920_000
ISSUER = "gradpath-next:local"
AUDIENCE = "gradpath-api:local"
KEY_ID = "web-local-2026-07"
SIGNING_SECRET = "request-context-signing-secret-2026-local"
AUDIT_SECRET = "audit-pseudonym-secret-2026-local-only"
REMOTE_POLICY_SHA256 = "sha256:7000cf54e5bb46c5732e660d40fa687339ffee19073f32b75e4693fd6b743a73"
STORAGE_POLICY_SHA256 = "sha256:fdde570f26e640b376885d9999ee956c6c6c395d02401acf1f23512089c5e7fa"
USER_ID = UUID("5f948a9a-3f0d-4a40-8a87-b676329c8062")
ANALYSIS_BODY = (
    b'{"allowRemoteProcessing":true,"jdText":"Build Python APIs","resumeText":"Built Python APIs"}'
)
STORAGE_BODY = b'{"contentFingerprint":"sha256:' + (b"a" * 64) + b'"}'
TOKEN_MUTATORS: tuple[Callable[[str], str], ...] = (
    lambda token: token.replace("v1.", "v2.", 1),
    lambda token: token + ".extra",
    lambda token: token.rsplit(".", maxsplit=1)[0] + ".bad+alphabet",
    lambda token: (
        token.split(".", maxsplit=2)[0]
        + "."
        + token.split(".", maxsplit=2)[1]
        + "=."
        + token.split(".", maxsplit=2)[2]
    ),
    lambda token: token[:-1] + ("A" if token[-1] != "A" else "B"),
)


def request_context_schema() -> Any:
    return importlib.import_module("app.schemas.request_context")


def request_context_service() -> Any:
    return importlib.import_module("app.services.request_context")


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def body_sha256(body: bytes) -> str:
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def consent(scope: str, *, attested_at: int = NOW - 2) -> dict[str, Any]:
    if scope == "remote_processing":
        return {
            "consentId": str(uuid4()),
            "scope": scope,
            "granted": True,
            "processor": "openrouter",
            "purpose": "resume_jd_readiness_analysis",
            "version": "remote-ai-v1",
            "policySha256": REMOTE_POLICY_SHA256,
            "attestedAt": attested_at,
        }
    return {
        "consentId": str(uuid4()),
        "scope": scope,
        "granted": True,
        "purpose": "private_jd_storage",
        "version": "private-storage-v1",
        "policySha256": STORAGE_POLICY_SHA256,
        "attestedAt": attested_at,
    }


def consents_with_duplicate_id() -> list[dict[str, Any]]:
    remote = consent("remote_processing")
    private = consent("private_jd_storage")
    private["consentId"] = remote["consentId"]
    return [remote, private]


def claims(
    *,
    body: bytes = ANALYSIS_BODY,
    action: str = "analysis.evaluate",
    now: int = NOW,
    **updates: Any,
) -> dict[str, Any]:
    is_analysis = action == "analysis.evaluate"
    payload: dict[str, Any] = {
        "v": 1,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "kid": KEY_ID,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + 60,
        "sub": f"authjs:{USER_ID}",
        "principalKind": "authenticated_user",
        "action": action,
        "method": "POST",
        "path": (
            "/api/v1/analyses/evaluate" if is_analysis else "/api/v1/job-descriptions/private"
        ),
        "query": "",
        "contentType": "application/json",
        "contentEncoding": "identity",
        "bodyLength": len(body),
        "bodySha256": body_sha256(body),
        "idempotencyKey": str(uuid4()),
        "consents": [consent("remote_processing" if is_analysis else "private_jd_storage")],
    }
    payload.update(updates)
    return payload


def sign_raw(payload_bytes: bytes, *, secret: str = SIGNING_SECRET, kid: str = KEY_ID) -> str:
    payload_segment = b64url(payload_bytes)
    signing_input = (
        b"gradpath.request-context.v1\n"
        + kid.encode("ascii")
        + b"\n"
        + payload_segment.encode("ascii")
    )
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"v1.{payload_segment}.{b64url(signature)}"


def sign_claims(payload: dict[str, Any], *, secret: str = SIGNING_SECRET) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return sign_raw(encoded, secret=secret, kid=str(payload.get("kid", KEY_ID)))


class MemoryReplayGuard:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.seen: set[tuple[str, str, UUID]] = set()
        self.calls: list[tuple[str, str, UUID, int]] = []

    async def consume(
        self,
        *,
        issuer: str,
        key_id: str,
        request_id: UUID,
        expires_at: int,
    ) -> bool:
        if not self.available:
            raise RuntimeError("replay store unavailable")
        key = (issuer, key_id, request_id)
        self.calls.append((*key, expires_at))
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


def verification_key(*, actions: frozenset[str] | None = None) -> Any:
    service = request_context_service()
    return service.RequestContextVerificationKey(
        secret=SecretStr(SIGNING_SECRET),
        issuer=ISSUER,
        audience=AUDIENCE,
        allowed_actions=(
            actions
            if actions is not None
            else frozenset({"analysis.evaluate", "catalog.persist.private"})
        ),
    )


def verify(
    token: str,
    *,
    body: bytes = ANALYSIS_BODY,
    action: str = "analysis.evaluate",
    method: str = "POST",
    path: str | None = None,
    query: str = "",
    content_type: str = "application/json",
    content_encoding: str = "identity",
    guard: MemoryReplayGuard | None = None,
    now: int = NOW,
    keys: dict[str, Any] | None = None,
) -> Any:
    service = request_context_service()
    replay_guard = guard or MemoryReplayGuard()
    expected_path = path or (
        "/api/v1/analyses/evaluate"
        if action == "analysis.evaluate"
        else "/api/v1/job-descriptions/private"
    )

    async def invoke() -> Any:
        return await service.verify_request_context(
            token,
            verification_keys=(keys if keys is not None else {KEY_ID: verification_key()}),
            expected_action=action,
            method=method,
            path=expected_path,
            query=query,
            content_type=content_type,
            content_encoding=content_encoding,
            body=body,
            replay_guard=replay_guard,
            now=datetime.fromtimestamp(now, UTC),
        )

    return run(invoke)


def test_valid_analysis_context_builds_only_an_authenticated_user_principal() -> None:
    service = request_context_service()
    payload = claims()
    guard = MemoryReplayGuard()

    context = verify(sign_claims(payload), guard=guard)

    assert context.principal == service.TrustedPrincipal(
        kind=service.PrincipalKind.AUTHENTICATED_USER,
        subject=f"authjs:{USER_ID}",
    )
    assert context.request_id == UUID(payload["jti"])
    assert context.idempotency_key == UUID(payload["idempotencyKey"])
    assert context.require_consent("remote_processing").granted is True
    assert guard.calls == [(ISSUER, KEY_ID, UUID(payload["jti"]), NOW + 75)]


def test_private_storage_uses_a_distinct_action_and_consent_scope() -> None:
    payload = claims(body=STORAGE_BODY, action="catalog.persist.private")

    context = verify(
        sign_claims(payload),
        body=STORAGE_BODY,
        action="catalog.persist.private",
    )

    assert context.action.value == "catalog.persist.private"
    assert context.require_consent("private_jd_storage").purpose == "private_jd_storage"


@pytest.mark.parametrize(
    "token_mutator",
    TOKEN_MUTATORS,
)
def test_token_grammar_signature_and_canonical_base64_are_strict(
    token_mutator: Callable[[str], str],
) -> None:
    service = request_context_service()
    token = token_mutator(sign_claims(claims()))

    with pytest.raises(service.RequestContextInvalid):
        verify(token)


@pytest.mark.parametrize(
    ("overrides", "verify_updates"),
    [
        ({}, {"body": ANALYSIS_BODY + b" "}),
        ({}, {"method": "PUT"}),
        ({}, {"path": "/api/v1/analyses/evaluate/"}),
        ({}, {"query": "debug=1"}),
        ({}, {"content_type": "application/json; charset=utf-8"}),
        ({}, {"content_encoding": "gzip"}),
        ({"bodyLength": len(ANALYSIS_BODY) + 1}, {}),
        ({"bodySha256": f"sha256:{'0' * 64}"}, {}),
    ],
)
def test_exact_method_path_query_headers_and_body_bytes_are_bound(
    overrides: dict[str, Any],
    verify_updates: dict[str, Any],
) -> None:
    service = request_context_service()
    guard = MemoryReplayGuard()
    token = sign_claims(claims(**overrides))

    with pytest.raises(service.RequestContextInvalid):
        verify(token, guard=guard, **verify_updates)
    assert guard.calls == []


@pytest.mark.parametrize(
    ("iat", "exp"),
    [
        (NOW - 120, NOW - 16),
        (NOW - 75, NOW - 15),
        (NOW + 16, NOW + 60),
        (NOW, NOW + 61),
        (NOW, NOW),
    ],
)
def test_time_window_is_short_and_skew_bounded(iat: int, exp: int) -> None:
    service = request_context_service()
    token = sign_claims(claims(iat=iat, exp=exp))

    with pytest.raises(service.RequestContextInvalid):
        verify(token)


@pytest.mark.parametrize(
    "updates",
    [
        {"sub": "student@bits-pilani.ac.in"},
        {"principalKind": "admin"},
        {"campusId": "bits-pilani"},
        {"unexpected": "field"},
        {"iat": float(NOW)},
        {"jti": str(UUID(int=0))},
        {"sub": f"authjs:{str(USER_ID).upper()}"},
    ],
)
def test_identity_privilege_and_claim_types_are_not_coercible(updates: dict[str, Any]) -> None:
    service = request_context_service()

    with pytest.raises(service.RequestContextInvalid):
        verify(sign_claims(claims(**updates)))


def test_duplicate_json_keys_are_rejected_even_with_a_valid_signature() -> None:
    service = request_context_service()
    encoded = json.dumps(claims(), separators=(",", ":"))
    duplicated = encoded.replace(
        f'"aud":"{AUDIENCE}"',
        f'"aud":"{AUDIENCE}","aud":"attacker-api"',
        1,
    ).encode("utf-8")

    with pytest.raises(service.RequestContextInvalid):
        verify(sign_raw(duplicated))


def test_deeply_nested_json_is_rejected_without_leaking_recursion_errors() -> None:
    service = request_context_service()
    nested_array = (b"[" * 3_500) + (b"]" * 3_500)
    unauthenticated = f"v1.{b64url(nested_array)}.{b64url(bytes(32))}"

    with pytest.raises(service.RequestContextInvalid):
        verify(unauthenticated)

    body = b'{"allowRemoteProcessing":' + nested_array + b"}"
    with pytest.raises(service.RequestContextInvalid):
        verify(sign_claims(claims(body=body)), body=body)


@pytest.mark.parametrize(
    "consents",
    [
        [],
        [consent("private_jd_storage")],
        [{**consent("remote_processing"), "granted": False}],
        [{**consent("remote_processing"), "processor": "unknown"}],
        [{**consent("remote_processing"), "purpose": "unrelated_processing"}],
        [{**consent("remote_processing"), "version": "remote-ai-v2"}],
        [{**consent("remote_processing"), "policySha256": STORAGE_POLICY_SHA256}],
        [consent("remote_processing", attested_at=NOW - 601)],
        [consent("remote_processing", attested_at=NOW + 16)],
    ],
)
def test_remote_processing_consent_is_explicit_fresh_and_action_specific(
    consents: list[dict[str, Any]],
) -> None:
    service = request_context_service()
    guard = MemoryReplayGuard()

    with pytest.raises(service.RequestContextConsentRequired):
        verify(sign_claims(claims(consents=consents)), guard=guard)
    assert guard.calls == []


@pytest.mark.parametrize(
    "consents",
    [
        [consent("remote_processing"), consent("remote_processing")],
        [consent("remote_processing"), consent("private_jd_storage")],
        consents_with_duplicate_id(),
    ],
)
def test_duplicate_or_unrelated_consent_attestations_are_invalid(
    consents: list[dict[str, Any]],
) -> None:
    service = request_context_service()
    guard = MemoryReplayGuard()

    with pytest.raises(service.RequestContextInvalid):
        verify(sign_claims(claims(consents=consents)), guard=guard)
    assert guard.calls == []


def test_consent_timestamp_is_bounded_by_verifier_time_not_only_issued_at() -> None:
    service = request_context_service()
    payload = claims(
        iat=NOW + 15,
        exp=NOW + 60,
        consents=[consent("remote_processing", attested_at=NOW + 30)],
    )

    with pytest.raises(service.RequestContextConsentRequired):
        verify(sign_claims(payload))


@pytest.mark.parametrize(
    "body",
    [
        ANALYSIS_BODY.replace(b"true", b"false", 1),
        ANALYSIS_BODY.replace(b"true", b'"yes"', 1),
    ],
)
def test_analysis_body_must_also_request_remote_processing(body: bytes) -> None:
    service = request_context_service()
    guard = MemoryReplayGuard()

    with pytest.raises(service.RequestContextConsentRequired):
        verify(sign_claims(claims(body=body)), body=body, guard=guard)
    assert guard.calls == []


def test_analysis_body_rejects_duplicate_remote_processing_keys() -> None:
    service = request_context_service()
    body = ANALYSIS_BODY.replace(
        b'{"allowRemoteProcessing":true',
        b'{"allowRemoteProcessing":true,"allowRemoteProcessing":true',
        1,
    )

    with pytest.raises(service.RequestContextInvalid):
        verify(sign_claims(claims(body=body)), body=body)


def test_replay_is_atomic_and_replay_store_failure_is_fail_closed() -> None:
    service = request_context_service()
    token = sign_claims(claims())
    guard = MemoryReplayGuard()

    verify(token, guard=guard)
    with pytest.raises(service.RequestContextReplayed):
        verify(token, guard=guard)

    unavailable = MemoryReplayGuard(available=False)
    with pytest.raises(service.RequestContextReplayStoreUnavailable):
        verify(sign_claims(claims()), guard=unavailable)


def test_key_policy_rejects_unknown_keys_wrong_environment_and_disallowed_action() -> None:
    service = request_context_service()
    token = sign_claims(claims())

    with pytest.raises(service.RequestContextInvalid):
        verify(token, keys={})
    with pytest.raises(service.RequestContextInvalid):
        verify(
            token,
            keys={
                KEY_ID: service.RequestContextVerificationKey(
                    secret=SecretStr(SIGNING_SECRET),
                    issuer="gradpath-next:production",
                    audience=AUDIENCE,
                    allowed_actions=frozenset({"analysis.evaluate"}),
                )
            },
        )
    with pytest.raises(service.RequestContextInvalid):
        verify(
            token,
            keys={
                KEY_ID: service.RequestContextVerificationKey(
                    secret=SecretStr(SIGNING_SECRET),
                    issuer=ISSUER,
                    audience="gradpath-api:production",
                    allowed_actions=frozenset({"analysis.evaluate"}),
                )
            },
        )
    with pytest.raises(service.RequestContextInvalid):
        verify(
            token, keys={KEY_ID: verification_key(actions=frozenset({"catalog.persist.private"}))}
        )
    with pytest.raises(service.RequestContextInvalid):
        verify(
            sign_claims(claims(body=STORAGE_BODY, action="catalog.persist.private")),
            body=STORAGE_BODY,
        )


def test_signature_authentication_precedes_consent_semantics() -> None:
    service = request_context_service()
    token = sign_claims(claims(consents=[]), secret="attacker-secret-that-is-long-enough-2026")

    with pytest.raises(service.RequestContextInvalid):
        verify(token)


def test_signing_and_audit_credentials_are_strong_unique_and_rotatable() -> None:
    settings = Settings.model_validate(
        {
            "internal_api_token": SecretStr("internal-token-that-is-long-and-unique"),
            "source_ingestion_token": SecretStr("ingestion-token-that-is-long-and-unique"),
            "request_context_signing_keys": {KEY_ID: SecretStr(SIGNING_SECRET)},
            "audit_pseudonym_secret": SecretStr(AUDIT_SECRET),
        }
    )
    configured = cast(dict[str, SecretStr], settings.model_dump()["request_context_signing_keys"])
    configured_secret = configured[KEY_ID]
    assert isinstance(configured_secret, SecretStr)
    assert configured_secret.get_secret_value() == SIGNING_SECRET

    for invalid in (
        {KEY_ID: SecretStr("short")},
        {KEY_ID: SecretStr("x" * 1_025)},
        {"invalid key id": SecretStr(SIGNING_SECRET)},
        {
            KEY_ID: SecretStr(SIGNING_SECRET),
            "web-local-old": SecretStr(SIGNING_SECRET),
        },
    ):
        with pytest.raises(ValidationError):
            Settings.model_validate({"request_context_signing_keys": invalid})

    for invalid_audit_secret in ("short", "x" * 1_025):
        with pytest.raises(ValidationError):
            Settings.model_validate({"audit_pseudonym_secret": SecretStr(invalid_audit_secret)})

    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "internal_api_token": SecretStr(SIGNING_SECRET),
                "request_context_signing_keys": {KEY_ID: SecretStr(SIGNING_SECRET)},
            }
        )
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "request_context_signing_keys": {KEY_ID: SecretStr(SIGNING_SECRET)},
                "audit_pseudonym_secret": SecretStr(SIGNING_SECRET),
            }
        )
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "source_ingestion_token": SecretStr(AUDIT_SECRET),
                "audit_pseudonym_secret": SecretStr(AUDIT_SECRET),
            }
        )
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "openrouter_api_key": SecretStr(SIGNING_SECRET),
                "request_context_signing_keys": {KEY_ID: SecretStr(SIGNING_SECRET)},
            }
        )

    service = request_context_service()
    with pytest.raises(ValueError):
        service.RequestContextVerificationKey(
            secret=SecretStr("short"),
            issuer=ISSUER,
            audience=AUDIENCE,
            allowed_actions=frozenset({"analysis.evaluate"}),
        )


def test_audit_event_is_content_free_and_pseudonymizes_request_and_subject() -> None:
    schema = request_context_schema()
    service = request_context_service()
    token = sign_claims(claims())
    context = verify(token)

    event = service.build_request_audit_event(
        context,
        outcome=schema.RequestAuditOutcome.AUTHORIZED,
        occurred_at=datetime.fromtimestamp(NOW, UTC),
        latency_ms=17,
        audit_secret=SecretStr(AUDIT_SECRET),
    )
    repeated = service.build_request_audit_event(
        context,
        outcome=schema.RequestAuditOutcome.AUTHORIZED,
        occurred_at=datetime.fromtimestamp(NOW, UTC),
        latency_ms=17,
        audit_secret=SecretStr(AUDIT_SECRET),
    )
    rotated = service.build_request_audit_event(
        context,
        outcome=schema.RequestAuditOutcome.AUTHORIZED,
        occurred_at=datetime.fromtimestamp(NOW, UTC),
        latency_ms=17,
        audit_secret=SecretStr("rotated-audit-pseudonym-secret-2026-local"),
    )

    alternate_payload = claims()
    alternate_context = verify(sign_claims(alternate_payload))
    alternate = service.build_request_audit_event(
        alternate_context,
        outcome=schema.RequestAuditOutcome.AUTHORIZED,
        occurred_at=datetime.fromtimestamp(NOW, UTC),
        latency_ms=17,
        audit_secret=SecretStr(AUDIT_SECRET),
    )

    serialized = event.model_dump_json()
    assert set(event.model_dump(by_alias=True)) == {
        "eventId",
        "occurredAt",
        "action",
        "outcome",
        "principalKind",
        "subjectPseudonym",
        "requestPseudonym",
        "keyId",
        "consentVersion",
        "consentGranted",
        "latencyMs",
        "errorCode",
    }
    assert re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", event.subject_pseudonym)
    assert re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", event.request_pseudonym)
    assert event.subject_pseudonym != event.request_pseudonym
    assert event.subject_pseudonym == repeated.subject_pseudonym
    assert event.request_pseudonym == repeated.request_pseudonym
    assert event.subject_pseudonym != rotated.subject_pseudonym
    assert event.request_pseudonym != rotated.request_pseudonym
    assert event.subject_pseudonym == alternate.subject_pseudonym
    assert event.request_pseudonym != alternate.request_pseudonym
    for forbidden in (
        "authjs:",
        token,
        claims()["bodySha256"],
        "resumeText",
        "jdText",
        "@",
        "https://",
    ):
        assert forbidden not in serialized
