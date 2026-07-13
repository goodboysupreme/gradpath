from typing import NamedTuple, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.base import Executable

from app.db.models.catalog import CatalogSource, JDProvenance, JobDescription, SourceRun
from app.schemas.domain import AccessLevel
from app.services.catalog_persistence import (
    CatalogPersistResult,
    CatalogWrite,
    PersistDisposition,
)


class CatalogSourceUnavailable(LookupError):
    pass


class CatalogPersistenceConflict(RuntimeError):
    pass


class CatalogSourceRunUnavailable(LookupError):
    pass


class RegisteredCatalogSource(NamedTuple):
    source_id: str
    source_account: str | None
    schema_version: str
    permission_basis: str
    status: str
    campus_id: str | None


class BoundSourceRun(NamedTuple):
    source_key: str
    actor_subject: str
    permission_basis: str
    status: str


def build_job_upsert(write: CatalogWrite, job_id: UUID) -> Executable:
    normalized = write.normalized
    source = normalized.source
    statement = insert(JobDescription).values(
        id=job_id,
        source_key=write.source_key,
        source_id=source.source_id.value,
        source_account=source.source_account,
        schema_version=source.schema_version,
        source_locator_fingerprint=source.source_locator_fingerprint,
        access_level=source.access_level.value,
        catalog_eligibility=source.catalog_eligibility.value,
        verification=source.verification.value,
        owner_subject=write.owner_subject,
        campus_id=write.campus_id,
        organization=normalized.organization,
        title=normalized.title,
        description=normalized.description,
        location=normalized.location,
        tracks=[track.value for track in normalized.tracks],
        opportunity_kind=normalized.opportunity_kind.value,
        application_url=(
            str(normalized.application_url) if normalized.application_url is not None else None
        ),
        published_at=normalized.published_at,
        application_deadline=normalized.application_deadline,
        content_fingerprint=normalized.content_fingerprint,
        fingerprint_version=normalized.fingerprint_version,
    )
    if source.access_level is AccessLevel.USER_PRIVATE:
        statement = statement.on_conflict_do_nothing(
            index_elements=(
                JobDescription.owner_subject,
                JobDescription.fingerprint_version,
                JobDescription.content_fingerprint,
            ),
            index_where=text("access_level = 'user_private'"),
        )
    elif source.access_level is AccessLevel.CAMPUS_RESTRICTED:
        statement = statement.on_conflict_do_nothing(
            index_elements=(
                JobDescription.campus_id,
                JobDescription.fingerprint_version,
                JobDescription.content_fingerprint,
            ),
            index_where=text("access_level = 'campus_restricted'"),
        )
    else:
        statement = statement.on_conflict_do_nothing(
            index_elements=(
                JobDescription.catalog_eligibility,
                JobDescription.fingerprint_version,
                JobDescription.content_fingerprint,
            ),
            index_where=text("access_level = 'public'"),
        )
    return statement.returning(JobDescription.id)


def build_provenance_insert(write: CatalogWrite, job_id: UUID) -> Executable:
    receipt = write.provenance
    return (
        insert(JDProvenance)
        .values(
            receipt_id=receipt.receipt_id,
            job_description_id=job_id,
            source_key=write.source_key,
            source_run_id=receipt.source_run_id,
            source_id=receipt.source_id,
            source_locator_fingerprint=receipt.source_locator_fingerprint,
            snapshot_fingerprint=receipt.snapshot_fingerprint,
            permission_basis=receipt.permission_basis,
            schema_version=receipt.schema_version,
            verification=receipt.verification,
            external_id=receipt.external_id,
            source_url=receipt.source_url,
            application_url=receipt.application_url,
            published_at=receipt.published_at,
            application_deadline=receipt.application_deadline,
            observed_at=receipt.observed_at,
            imported_by_subject=write.actor_subject,
        )
        .on_conflict_do_nothing(index_elements=(JDProvenance.receipt_id,))
        .returning(JDProvenance.receipt_id)
    )


class PostgresCatalogRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist(self, write: CatalogWrite) -> CatalogPersistResult:
        candidate_id = uuid4()
        async with self._session_factory.begin() as session:
            await _set_rls_context(session, write)
            await _require_registered_source(session, write)
            await _require_bound_source_run(session, write)

            result = await session.execute(build_job_upsert(write, candidate_id))
            inserted_id = cast(UUID | None, result.scalar_one_or_none())
            if inserted_id is None:
                existing_id = await session.scalar(_existing_job_select(write))
                if existing_id is None:
                    raise CatalogPersistenceConflict(
                        "catalog dedupe conflict could not be resolved"
                    )
                job_id = existing_id
                disposition = PersistDisposition.DEDUPLICATED
            else:
                job_id = inserted_id
                disposition = PersistDisposition.CREATED

            await _record_or_verify_provenance(session, write, job_id)
            return CatalogPersistResult(
                job_description_id=job_id,
                disposition=disposition,
            )


async def _require_registered_source(session: AsyncSession, write: CatalogWrite) -> None:
    registration = (
        (
            await session.execute(
                select(
                    CatalogSource.source_id,
                    CatalogSource.source_account,
                    CatalogSource.schema_version,
                    CatalogSource.permission_basis,
                    CatalogSource.status,
                    CatalogSource.campus_id,
                ).where(CatalogSource.source_key == write.source_key)
            )
        )
        .tuples()
        .one_or_none()
    )
    if registration is None:
        raise CatalogSourceUnavailable("catalog source is not registered and active")

    validate_registered_source(write, RegisteredCatalogSource(*registration))


def validate_registered_source(
    write: CatalogWrite,
    registration: RegisteredCatalogSource,
) -> None:
    source = write.normalized.source
    if (
        registration.status != "active"
        or registration.source_id != source.source_id.value
        or registration.source_account != source.source_account
        or registration.schema_version != source.schema_version
        or registration.permission_basis != source.permission_basis.value
        or registration.campus_id != write.campus_id
    ):
        raise CatalogSourceUnavailable("catalog source registration does not authorize this write")


async def _require_bound_source_run(session: AsyncSession, write: CatalogWrite) -> None:
    source_run_id = write.provenance.source_run_id
    if source_run_id is None:
        if write.normalized.source.access_level is AccessLevel.USER_PRIVATE:
            return
        raise CatalogSourceRunUnavailable("privileged catalog writes require a recorded source run")
    if write.normalized.source.access_level is AccessLevel.USER_PRIVATE:
        raise CatalogSourceRunUnavailable("direct user uploads cannot reference a source run")

    source_run = (
        (
            await session.execute(
                select(
                    SourceRun.source_key,
                    SourceRun.actor_subject,
                    SourceRun.permission_basis,
                    SourceRun.status,
                ).where(SourceRun.id == source_run_id)
            )
        )
        .tuples()
        .one_or_none()
    )
    if source_run is None:
        raise CatalogSourceRunUnavailable("catalog source run is unavailable for this write")

    validate_bound_source_run(write, BoundSourceRun(*source_run))


def validate_bound_source_run(write: CatalogWrite, source_run: BoundSourceRun) -> None:
    if (
        source_run.source_key != write.source_key
        or source_run.actor_subject != write.actor_subject
        or source_run.permission_basis != write.normalized.source.permission_basis.value
        or source_run.status not in {"started", "completed"}
    ):
        raise CatalogSourceRunUnavailable("catalog source run does not authorize this write")


async def _record_or_verify_provenance(
    session: AsyncSession,
    write: CatalogWrite,
    job_id: UUID,
) -> None:
    result = await session.execute(build_provenance_insert(write, job_id))
    inserted_receipt_id = cast(UUID | None, result.scalar_one_or_none())
    if inserted_receipt_id is not None:
        return

    existing = await session.get(JDProvenance, write.provenance.receipt_id)
    receipt = write.provenance
    if existing is None or (
        existing.job_description_id,
        existing.source_key,
        existing.source_run_id,
        existing.source_id,
        existing.source_locator_fingerprint,
        existing.snapshot_fingerprint,
        existing.permission_basis,
        existing.schema_version,
        existing.verification,
        existing.external_id,
        existing.source_url,
        existing.application_url,
        existing.published_at,
        existing.application_deadline,
        existing.observed_at,
        existing.imported_by_subject,
    ) != (
        job_id,
        write.source_key,
        receipt.source_run_id,
        receipt.source_id,
        receipt.source_locator_fingerprint,
        receipt.snapshot_fingerprint,
        receipt.permission_basis,
        receipt.schema_version,
        receipt.verification,
        receipt.external_id,
        receipt.source_url,
        receipt.application_url,
        receipt.published_at,
        receipt.application_deadline,
        receipt.observed_at,
        write.actor_subject,
    ):
        raise CatalogPersistenceConflict("provenance receipt conflicts with an existing binding")


async def _set_rls_context(session: AsyncSession, write: CatalogWrite) -> None:
    settings = {
        "app.actor_kind": write.principal_kind.value,
        "app.actor_subject": write.actor_subject,
        "app.campus_id": write.campus_id or "",
        "app.owner_subject": write.owner_subject or "",
    }
    for key, value in settings.items():
        await session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": key, "value": value},
        )


def _existing_job_select(write: CatalogWrite) -> Select[tuple[UUID]]:
    source = write.normalized.source
    statement = select(JobDescription.id).where(
        JobDescription.access_level == source.access_level.value,
        JobDescription.fingerprint_version == write.normalized.fingerprint_version,
        JobDescription.content_fingerprint == write.normalized.content_fingerprint,
    )
    if source.access_level is AccessLevel.USER_PRIVATE:
        return statement.where(JobDescription.owner_subject == write.owner_subject)
    if source.access_level is AccessLevel.CAMPUS_RESTRICTED:
        return statement.where(JobDescription.campus_id == write.campus_id)
    return statement.where(
        JobDescription.catalog_eligibility == source.catalog_eligibility.value,
    )
