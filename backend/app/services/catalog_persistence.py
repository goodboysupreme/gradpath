import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.schemas.domain import AccessLevel
from app.schemas.job_sources import (
    CatalogEligibility,
    NormalizedJobDescriptionResponse,
)


class PrincipalKind(StrEnum):
    AUTHENTICATED_USER = "authenticated_user"
    SHARED_GUEST = "shared_guest"
    CAMPUS_CURATOR = "campus_curator"
    CONNECTOR = "connector"
    ADMIN = "admin"


class PersistDisposition(StrEnum):
    CREATED = "created"
    DEDUPLICATED = "deduplicated"


class CatalogPersistenceAuthorizationError(PermissionError):
    pass


class PrivateCatalogSaveForbidden(CatalogPersistenceAuthorizationError):
    pass


@dataclass(frozen=True, slots=True)
class TrustedPrincipal:
    kind: PrincipalKind
    subject: str
    campus_id: str | None = None

    def __post_init__(self) -> None:
        if not 3 <= len(self.subject) <= 320 or ":" not in self.subject:
            raise ValueError("principal subject must be issuer-qualified")
        if self.campus_id is not None and not 2 <= len(self.campus_id) <= 160:
            raise ValueError("campus identifier is invalid")
        if self.kind is PrincipalKind.CAMPUS_CURATOR and self.campus_id is None:
            raise ValueError("campus curators require a verified campus identifier")


@dataclass(frozen=True, slots=True)
class CatalogProvenanceReceipt:
    receipt_id: UUID
    source_run_id: UUID | None
    source_id: str
    source_locator_fingerprint: str
    snapshot_fingerprint: str
    permission_basis: str
    schema_version: str
    verification: str
    external_id: str | None
    source_url: str | None
    application_url: str | None
    published_at: datetime | None
    application_deadline: datetime | None
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogWrite:
    normalized: NormalizedJobDescriptionResponse
    dedupe_key: str
    source_key: str
    owner_subject: str | None
    campus_id: str | None
    actor_subject: str
    principal_kind: PrincipalKind
    provenance: CatalogProvenanceReceipt


@dataclass(frozen=True, slots=True)
class CatalogPersistResult:
    job_description_id: UUID
    disposition: PersistDisposition


class CatalogWriter(Protocol):
    async def persist(self, write: CatalogWrite) -> CatalogPersistResult: ...


def build_catalog_write(
    actor: TrustedPrincipal,
    normalized: NormalizedJobDescriptionResponse,
    *,
    receipt_id: UUID,
    source_run_id: UUID | None = None,
) -> CatalogWrite:
    owner_subject, campus_id = _scope_for(actor, normalized)
    is_private_upload = normalized.source.access_level is AccessLevel.USER_PRIVATE
    if is_private_upload and source_run_id is not None:
        raise CatalogPersistenceAuthorizationError(
            "direct user uploads cannot claim a privileged source run"
        )
    if not is_private_upload and source_run_id is None:
        raise CatalogPersistenceAuthorizationError(
            "privileged catalog writes require a recorded source run"
        )
    source_key = _source_key(normalized, campus_id=campus_id)
    dedupe_key = _dedupe_key(
        normalized,
        owner_subject=owner_subject,
        campus_id=campus_id,
    )
    source = normalized.source
    return CatalogWrite(
        normalized=normalized,
        dedupe_key=dedupe_key,
        source_key=source_key,
        owner_subject=owner_subject,
        campus_id=campus_id,
        actor_subject=actor.subject,
        principal_kind=actor.kind,
        provenance=CatalogProvenanceReceipt(
            receipt_id=receipt_id,
            source_run_id=source_run_id,
            source_id=source.source_id.value,
            source_locator_fingerprint=source.source_locator_fingerprint,
            snapshot_fingerprint=normalized.content_fingerprint,
            permission_basis=source.permission_basis.value,
            schema_version=source.schema_version,
            verification=source.verification.value,
            external_id=source.external_id,
            source_url=str(source.source_url) if source.source_url is not None else None,
            application_url=(
                str(normalized.application_url) if normalized.application_url is not None else None
            ),
            published_at=normalized.published_at,
            application_deadline=normalized.application_deadline,
            observed_at=source.observed_at,
        ),
    )


async def persist_normalized_jd(
    actor: TrustedPrincipal,
    normalized: NormalizedJobDescriptionResponse,
    repository: CatalogWriter,
    *,
    receipt_id: UUID,
    source_run_id: UUID | None = None,
) -> CatalogPersistResult:
    write = build_catalog_write(
        actor,
        normalized,
        receipt_id=receipt_id,
        source_run_id=source_run_id,
    )
    return await repository.persist(write)


def _scope_for(
    actor: TrustedPrincipal,
    normalized: NormalizedJobDescriptionResponse,
) -> tuple[str | None, str | None]:
    access_level = normalized.source.access_level
    if actor.kind is PrincipalKind.SHARED_GUEST:
        if access_level is AccessLevel.USER_PRIVATE:
            raise PrivateCatalogSaveForbidden("shared guests cannot persist private catalog data")
        raise CatalogPersistenceAuthorizationError("shared guests cannot persist catalog data")
    if access_level is AccessLevel.USER_PRIVATE:
        if actor.kind is not PrincipalKind.AUTHENTICATED_USER:
            raise PrivateCatalogSaveForbidden(
                "private catalog writes require an authenticated user"
            )
        return actor.subject, None
    if access_level is AccessLevel.CAMPUS_RESTRICTED:
        if actor.kind not in {PrincipalKind.CAMPUS_CURATOR, PrincipalKind.ADMIN}:
            raise CatalogPersistenceAuthorizationError(
                "campus catalog writes require a trusted curator"
            )
        if actor.campus_id is None:
            raise CatalogPersistenceAuthorizationError(
                "campus catalog writes require a verified campus"
            )
        return None, actor.campus_id

    eligibility = normalized.source.catalog_eligibility
    if eligibility is CatalogEligibility.PRACTICE_ONLY:
        if actor.kind is not PrincipalKind.ADMIN:
            raise CatalogPersistenceAuthorizationError(
                "practice catalog writes require an administrator"
            )
    elif actor.kind not in {PrincipalKind.CONNECTOR, PrincipalKind.ADMIN}:
        raise CatalogPersistenceAuthorizationError(
            "public catalog writes require a trusted connector"
        )
    return None, None


def _source_key(
    normalized: NormalizedJobDescriptionResponse,
    *,
    campus_id: str | None,
) -> str:
    source = normalized.source
    if source.source_account is None:
        return source.source_id.value
    canonical = json.dumps(
        {
            "account": source.source_account.casefold(),
            "campusId": campus_id.casefold() if campus_id is not None else None,
            "domain": "gradpath.catalog.source",
            "sourceId": source.source_id.value,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    source_digest = hashlib.sha256(canonical).hexdigest()
    return f"{source.source_id.value}:sha256:{source_digest}"


def _dedupe_key(
    normalized: NormalizedJobDescriptionResponse,
    *,
    owner_subject: str | None,
    campus_id: str | None,
) -> str:
    source = normalized.source
    if source.access_level is AccessLevel.USER_PRIVATE:
        scope: dict[str, object] = {
            "accessLevel": source.access_level.value,
            "ownerSubject": owner_subject,
        }
    elif source.access_level is AccessLevel.CAMPUS_RESTRICTED:
        scope = {
            "accessLevel": source.access_level.value,
            "campusId": campus_id,
        }
    else:
        scope = {
            "accessLevel": source.access_level.value,
            "catalogEligibility": source.catalog_eligibility.value,
        }
    canonical = json.dumps(
        {
            "contentFingerprint": normalized.content_fingerprint,
            "domain": "gradpath.catalog.dedupe",
            "fingerprintVersion": normalized.fingerprint_version,
            "scope": scope,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
