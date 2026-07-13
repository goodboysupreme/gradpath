import importlib
import io
from dataclasses import fields
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from anyio import run
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.schemas.job_sources import JobDescriptionNormalizationRequest
from app.services.job_sources import normalize_job_description

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def persistence_models() -> Any:
    return importlib.import_module("app.db.models.catalog")


def persistence_service() -> Any:
    return importlib.import_module("app.services.catalog_persistence")


def persistence_repository() -> Any:
    return importlib.import_module("app.repositories.catalog")


def normalized_payload(**updates: Any) -> Any:
    payload: dict[str, Any] = {
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
    payload.update(updates)
    request = JobDescriptionNormalizationRequest.model_validate(payload)
    return normalize_job_description(request)


def principal(
    kind: str,
    subject: str,
    *,
    campus_id: str | None = None,
) -> Any:
    service = persistence_service()
    return service.TrustedPrincipal(
        kind=service.PrincipalKind(kind),
        subject=subject,
        campus_id=campus_id,
    )


def build_write(
    normalized: Any,
    actor: Any,
    *,
    receipt_id: UUID | None = None,
    source_run_id: UUID | None = None,
) -> Any:
    service = persistence_service()
    return service.build_catalog_write(
        actor,
        normalized,
        receipt_id=receipt_id or uuid4(),
        source_run_id=source_run_id,
    )


def test_catalog_metadata_isolated_in_career_catalog_schema() -> None:
    models = persistence_models()
    metadata = models.Base.metadata

    assert set(metadata.tables) == {
        "career_catalog.catalog_sources",
        "career_catalog.source_runs",
        "career_catalog.job_descriptions",
        "career_catalog.jd_provenance",
    }
    for table in metadata.tables.values():
        assert table.schema == "career_catalog"
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table.schema == "career_catalog"

    jobs = metadata.tables["career_catalog.job_descriptions"]
    assert jobs.c.owner_subject.foreign_keys == set()
    assert "user_id" not in jobs.c
    assert "public.users" not in str(metadata.tables)


def test_postgresql_exact_dedupe_indexes_are_access_scoped() -> None:
    jobs = persistence_models().Base.metadata.tables["career_catalog.job_descriptions"]
    indexes = {index.name: index for index in jobs.indexes}
    expected_columns = {
        "uq_job_descriptions_private_exact": (
            "owner_subject",
            "fingerprint_version",
            "content_fingerprint",
        ),
        "uq_job_descriptions_campus_exact": (
            "campus_id",
            "fingerprint_version",
            "content_fingerprint",
        ),
        "uq_job_descriptions_public_source_revision": (
            "source_id",
            "source_account",
            "schema_version",
            "source_locator_fingerprint",
            "fingerprint_version",
            "content_fingerprint",
        ),
    }

    assert expected_columns.keys() <= indexes.keys()
    for name, columns in expected_columns.items():
        index = indexes[name]
        assert index.unique is True
        assert tuple(expression.name for expression in index.expressions) == columns
        sql = str(CreateIndex(index).compile(dialect=postgresql.dialect())).lower()
        assert " where " in sql

    assert "access_level = 'user_private'" in str(
        indexes["uq_job_descriptions_private_exact"].dialect_options["postgresql"]["where"]
    )
    assert "access_level = 'campus_restricted'" in str(
        indexes["uq_job_descriptions_campus_exact"].dialect_options["postgresql"]["where"]
    )
    assert "access_level = 'public'" in str(
        indexes["uq_job_descriptions_public_source_revision"].dialect_options["postgresql"]["where"]
    )


def test_scope_constraints_require_correct_owner_and_preserve_synthetic_status() -> None:
    jobs = persistence_models().Base.metadata.tables["career_catalog.job_descriptions"]
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in jobs.constraints
        if constraint.name is not None and hasattr(constraint, "sqltext")
    }

    scope = checks["ck_job_descriptions_scope"]
    assert "user_private" in scope
    assert "owner_subject IS NOT NULL" in scope
    assert "campus_restricted" in scope
    assert "campus_id IS NOT NULL" in scope
    assert "public" in scope
    assert "owner_subject IS NULL" in scope
    assert "campus_id IS NULL" in scope

    synthetic = checks["ck_job_descriptions_synthetic_eligibility"]
    assert "synthetic_practice" in synthetic
    assert "practice_only" in synthetic


def test_shared_guest_cannot_save_private_jd() -> None:
    service = persistence_service()
    repository_module = persistence_repository()

    class RecordingRepository:
        def __init__(self) -> None:
            self.calls: list[Any] = []

        async def persist(self, write: Any) -> Any:
            self.calls.append(write)
            return repository_module.CatalogPersistResult(
                job_description_id=uuid4(),
                disposition=repository_module.PersistDisposition.CREATED,
            )

    repository = RecordingRepository()
    guest = principal("shared_guest", "guest:gradpath-shared")

    async def invoke() -> None:
        await service.persist_normalized_jd(
            guest,
            normalized_payload(),
            repository,
            receipt_id=uuid4(),
        )

    with pytest.raises(service.PrivateCatalogSaveForbidden):
        run(invoke)
    assert repository.calls == []


def test_dedupe_keys_preserve_tenant_and_trust_boundaries() -> None:
    private = normalized_payload()
    private_a = build_write(private, principal("authenticated_user", "authjs:user-a"))
    private_a_again = build_write(
        private,
        principal("authenticated_user", "authjs:user-a"),
    )
    private_b = build_write(private, principal("authenticated_user", "authjs:user-b"))
    assert private_a.dedupe_key == private_a_again.dedupe_key
    assert private_a.dedupe_key != private_b.dedupe_key

    campus = normalized_payload(
        sourceId="campus_authorized",
        permissionBasis="placement_cell_authorized",
        sourceAccount="bits-si-2026",
        externalId="SI-42",
        authorizationRef="encrypted-outside-normalized-output",
    )
    campus_pilani = build_write(
        campus,
        principal("campus_curator", "authjs:curator-a", campus_id="bits-pilani"),
    )
    campus_goa = build_write(
        campus,
        principal("campus_curator", "authjs:curator-b", campus_id="bits-goa"),
    )
    assert campus_pilani.dedupe_key != campus_goa.dedupe_key

    public_live = normalized_payload(
        sourceId="greenhouse",
        permissionBasis="public_api_terms_reviewed",
        sourceAccount="acme-board",
        externalId="1234567",
        sourceUrl="https://boards.greenhouse.io/acme/jobs/1234567",
        applicationUrl="https://boards.greenhouse.io/acme/jobs/1234567",
        schemaVersion="greenhouse-job-board-v1",
    )
    practice = normalized_payload(
        sourceId="synthetic_practice",
        permissionBasis="internal_practice",
        sourceAccount="gradpath-samples-v1",
        externalId="sde-intern-sample",
        schemaVersion="synthetic-v1",
    )
    live_write = build_write(
        public_live,
        principal("connector", "service:greenhouse-connector"),
    )
    practice_write = build_write(
        practice,
        principal("admin", "authjs:catalog-admin"),
    )
    assert public_live.content_fingerprint == practice.content_fingerprint
    assert live_write.dedupe_key != practice_write.dedupe_key


def test_duplicate_content_keeps_distinct_provenance_receipts() -> None:
    service = persistence_service()
    repository_module = persistence_repository()

    class IdempotentRepository:
        def __init__(self) -> None:
            self.jobs: dict[str, UUID] = {}
            self.receipts: list[Any] = []

        async def persist(self, write: Any) -> Any:
            existing_id = self.jobs.get(write.dedupe_key)
            job_id = existing_id or uuid4()
            self.jobs[write.dedupe_key] = job_id
            self.receipts.append(write.provenance)
            disposition = (
                repository_module.PersistDisposition.DEDUPLICATED
                if existing_id is not None
                else repository_module.PersistDisposition.CREATED
            )
            return repository_module.CatalogPersistResult(
                job_description_id=job_id,
                disposition=disposition,
            )

    repository = IdempotentRepository()
    actor = principal("authenticated_user", "authjs:user-a")
    normalized = normalized_payload()
    first_run = uuid4()
    second_run = uuid4()

    async def invoke() -> tuple[Any, Any]:
        first = await service.persist_normalized_jd(
            actor,
            normalized,
            repository,
            receipt_id=uuid4(),
            source_run_id=first_run,
        )
        second = await service.persist_normalized_jd(
            actor,
            normalized,
            repository,
            receipt_id=uuid4(),
            source_run_id=second_run,
        )
        return first, second

    first, second = run(invoke)
    assert first.job_description_id == second.job_description_id
    assert first.disposition is repository_module.PersistDisposition.CREATED
    assert second.disposition is repository_module.PersistDisposition.DEDUPLICATED
    assert len(repository.jobs) == 1
    assert [receipt.source_run_id for receipt in repository.receipts] == [
        first_run,
        second_run,
    ]
    provenance_fields = {field.name for field in fields(repository.receipts[0])}
    assert {
        "receipt_id",
        "source_run_id",
        "source_id",
        "source_locator_fingerprint",
        "permission_basis",
        "schema_version",
        "verification",
        "observed_at",
    } <= provenance_fields
    assert not {"authorization_ref", "authorization_reference"} & provenance_fields


def test_postgres_dml_uses_partial_conflict_targets_and_idempotent_receipts() -> None:
    repository = persistence_repository()
    private_write = build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
    )
    private_sql = str(
        repository.build_job_upsert(private_write, uuid4()).compile(
            dialect=postgresql.dialect(),
        )
    ).lower()
    assert "on conflict (owner_subject, fingerprint_version, content_fingerprint)" in private_sql
    assert "access_level =" in private_sql
    assert "do nothing" in private_sql

    provenance_sql = str(
        repository.build_provenance_insert(private_write, uuid4()).compile(
            dialect=postgresql.dialect(),
        )
    ).lower()
    assert "on conflict (receipt_id) do nothing" in provenance_sql


def test_alembic_upgrade_renders_isolated_postgresql_ddl_offline() -> None:
    output = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+asyncpg://offline:offline@localhost/offline",
    )

    command.upgrade(config, "head", sql=True)

    sql = output.getvalue().lower()
    assert "create schema if not exists career_catalog" in sql
    for table in (
        "catalog_sources",
        "source_runs",
        "job_descriptions",
        "jd_provenance",
    ):
        assert f"create table career_catalog.{table}" in sql
    for index in (
        "uq_job_descriptions_private_exact",
        "uq_job_descriptions_campus_exact",
        "uq_job_descriptions_public_source_revision",
    ):
        assert f"create unique index {index}" in sql
    assert "enable row level security" in sql
    assert "force row level security" in sql
    assert "prevent_job_description_mutation" in sql
    assert "prevent_provenance_mutation" in sql
    assert "references public.users" not in sql
    assert "alter table public." not in sql


def test_alembic_downgrade_only_removes_owned_catalog_tables() -> None:
    output = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)
    config.set_main_option(
        "sqlalchemy.url",
        "postgresql+asyncpg://offline:offline@localhost/offline",
    )

    command.downgrade(config, "head:base", sql=True)

    sql = output.getvalue().lower()
    for table in (
        "jd_provenance",
        "job_descriptions",
        "source_runs",
        "catalog_sources",
    ):
        assert f"drop table career_catalog.{table}" in sql
    assert "drop schema career_catalog" not in sql
    assert "drop table public." not in sql
    assert "drop schema public" not in sql
