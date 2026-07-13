import importlib
import io
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from anyio import run
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
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


def normalized_greenhouse() -> Any:
    return normalized_payload(
        sourceId="greenhouse",
        permissionBasis="public_api_terms_reviewed",
        sourceAccount="acme-board",
        externalId="1234567",
        sourceUrl="https://boards.greenhouse.io/acme/jobs/1234567",
        applicationUrl="https://boards.greenhouse.io/acme/jobs/1234567",
        publishedAt="2026-07-01T09:00:00+05:30",
        applicationDeadline="2026-08-01T23:59:00+05:30",
        schemaVersion="greenhouse-job-board-v1",
        tracks=["off_campus"],
    )


def normalized_lever() -> Any:
    return normalized_payload(
        sourceId="lever",
        permissionBasis="public_api_terms_reviewed",
        sourceAccount="acme",
        externalId="lever-posting-42",
        sourceUrl="https://jobs.lever.co/acme/lever-posting-42",
        applicationUrl="https://jobs.lever.co/acme/lever-posting-42",
        publishedAt="2026-07-02T10:00:00+05:30",
        applicationDeadline="2026-08-15T23:59:00+05:30",
        schemaVersion="lever-postings-v0",
        tracks=["off_campus"],
    )


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


class ReplayResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def scalar_one_or_none(self) -> Any:
        return self.value

    def one_or_none(self) -> Any:
        return self.value

    def tuples(self) -> "ReplayResult":
        return self

    def mappings(self) -> "ReplayResult":
        if isinstance(self.value, SimpleNamespace):
            return ReplayResult(vars(self.value))
        return self


class ReplaySession:
    def __init__(self, job_id: UUID, existing_receipt: Any) -> None:
        self.job_id = job_id
        self.existing_receipt = existing_receipt
        self.provenance_lookup_count = 0

    async def execute(
        self,
        statement: Any,
        parameters: Any | None = None,
    ) -> ReplayResult:
        if parameters is not None:
            return ReplayResult(None)
        table_name = getattr(getattr(statement, "table", None), "name", None)
        if table_name in {"job_descriptions", "jd_provenance"}:
            return ReplayResult(None)
        sql = str(statement)
        if "catalog_sources" in sql:
            return ReplayResult(
                (
                    "user_upload",
                    None,
                    "manual-v1",
                    "user_provided",
                    "active",
                    None,
                )
            )
        if "jd_provenance" in sql:
            self.provenance_lookup_count += 1
            return ReplayResult(self.existing_receipt)
        return ReplayResult(None)

    async def scalar(self, statement: Any) -> Any:
        sql = str(statement)
        if "jd_provenance" in sql:
            self.provenance_lookup_count += 1
            return self.existing_receipt
        if "catalog_sources" in sql:
            return "active"
        if "job_descriptions" in sql:
            return self.job_id
        return None

    async def get(self, _model: Any, _identity: Any) -> Any:
        self.provenance_lookup_count += 1
        return self.existing_receipt


class ReplayContext:
    def __init__(self, session: ReplaySession) -> None:
        self.session = session

    async def __aenter__(self) -> ReplaySession:
        return self.session

    async def __aexit__(self, *_error: Any) -> None:
        return None


class ReplaySessionFactory:
    def __init__(self, session: ReplaySession) -> None:
        self.session = session

    def begin(self) -> ReplayContext:
        return ReplayContext(self.session)


def stored_receipt(write: Any, job_id: UUID, **updates: Any) -> Any:
    receipt = write.provenance
    values: dict[str, Any] = {
        "receipt_id": receipt.receipt_id,
        "job_description_id": job_id,
        "source_key": write.source_key,
        "source_run_id": receipt.source_run_id,
        "source_id": receipt.source_id,
        "source_locator_fingerprint": receipt.source_locator_fingerprint,
        "snapshot_fingerprint": receipt.snapshot_fingerprint,
        "permission_basis": receipt.permission_basis,
        "schema_version": receipt.schema_version,
        "verification": receipt.verification,
        "external_id": receipt.external_id,
        "source_url": receipt.source_url,
        "application_url": receipt.application_url,
        "published_at": receipt.published_at,
        "application_deadline": receipt.application_deadline,
        "observed_at": receipt.observed_at,
        "imported_by_subject": write.actor_subject,
    }
    values.update(updates)
    return SimpleNamespace(**values)


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


def test_sources_and_runs_are_bound_to_every_privileged_receipt() -> None:
    metadata = persistence_models().Base.metadata
    sources = metadata.tables["career_catalog.catalog_sources"]
    runs = metadata.tables["career_catalog.source_runs"]
    jobs = metadata.tables["career_catalog.job_descriptions"]
    provenance = metadata.tables["career_catalog.jd_provenance"]
    assert {"application_url", "published_at", "application_deadline"} <= set(provenance.c.keys())
    provenance_checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in provenance.constraints
        if constraint.name is not None and hasattr(constraint, "sqltext")
    }
    assert (
        "application_deadline >= published_at"
        in provenance_checks["ck_jd_provenance_listing_dates"]
    )
    source_provenance = provenance_checks["ck_jd_provenance_source_provenance"]
    assert "application_url IS NULL" in source_provenance
    assert "published_at IS NULL" in source_provenance
    assert "application_deadline IS NULL" in source_provenance

    source_checks = tuple(
        str(constraint.sqltext)
        for constraint in sources.constraints
        if hasattr(constraint, "sqltext")
    )
    assert any("source_key ~" in check and "sha256" in check for check in source_checks)

    for table in (runs, jobs, provenance):
        assert any(
            foreign_key.column.table is sources and foreign_key.parent.name == "source_key"
            for foreign_key in table.foreign_keys
        )

    run_identity = ("id", "source_key", "permission_basis", "actor_subject")
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == run_identity
        for constraint in runs.constraints
    )

    expected_targets = (
        "career_catalog.source_runs.id",
        "career_catalog.source_runs.source_key",
        "career_catalog.source_runs.permission_basis",
        "career_catalog.source_runs.actor_subject",
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and tuple(constraint.column_keys)
        == ("source_run_id", "source_key", "permission_basis", "imported_by_subject")
        and tuple(element.target_fullname for element in constraint.elements) == expected_targets
        for constraint in provenance.constraints
    )


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
        "uq_job_descriptions_public_exact": (
            "catalog_eligibility",
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
        indexes["uq_job_descriptions_public_exact"].dialect_options["postgresql"]["where"]
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
        source_run_id=uuid4(),
    )
    campus_goa = build_write(
        campus,
        principal("campus_curator", "authjs:curator-b", campus_id="bits-goa"),
        source_run_id=uuid4(),
    )
    assert campus_pilani.dedupe_key != campus_goa.dedupe_key
    assert campus_pilani.source_key != campus_goa.source_key

    public_live = normalized_greenhouse()
    practice = normalized_payload(
        sourceId="synthetic_practice",
        permissionBasis="internal_practice",
        sourceAccount="gradpath-samples-v1",
        externalId="sde-intern-sample",
        schemaVersion="synthetic-v1",
        tracks=["off_campus"],
    )
    live_write = build_write(
        public_live,
        principal("connector", "service:greenhouse-connector"),
        source_run_id=uuid4(),
    )
    practice_write = build_write(
        practice,
        principal("admin", "authjs:catalog-admin"),
        source_run_id=uuid4(),
    )
    assert public_live.content_fingerprint == practice.content_fingerprint
    assert live_write.dedupe_key != practice_write.dedupe_key


def test_privileged_catalog_writes_require_a_recorded_source_run() -> None:
    service = persistence_service()
    campus = normalized_payload(
        sourceId="campus_authorized",
        permissionBasis="placement_cell_authorized",
        sourceAccount="bits-si-2026",
        externalId="SI-42",
        authorizationRef="encrypted-outside-normalized-output",
    )
    practice = normalized_payload(
        sourceId="synthetic_practice",
        permissionBasis="internal_practice",
        sourceAccount="gradpath-samples-v1",
        externalId="sde-intern-sample",
        schemaVersion="synthetic-v1",
    )

    privileged_writes = (
        (
            campus,
            principal("campus_curator", "authjs:curator", campus_id="bits-pilani"),
        ),
        (
            normalized_greenhouse(),
            principal("connector", "service:greenhouse-connector"),
        ),
        (practice, principal("admin", "authjs:catalog-admin")),
    )
    for normalized, actor in privileged_writes:
        with pytest.raises(service.CatalogPersistenceAuthorizationError):
            build_write(normalized, actor)

    build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
    )
    with pytest.raises(service.CatalogPersistenceAuthorizationError):
        build_write(
            normalized_payload(),
            principal("authenticated_user", "authjs:user-a"),
            source_run_id=uuid4(),
        )


def test_source_registration_must_exactly_authorize_the_write() -> None:
    repository = persistence_repository()
    write = build_write(
        normalized_greenhouse(),
        principal("connector", "service:greenhouse-connector"),
        source_run_id=uuid4(),
    )
    exact = repository.RegisteredCatalogSource(
        source_id="greenhouse",
        source_account="acme-board",
        schema_version="greenhouse-job-board-v1",
        permission_basis="public_api_terms_reviewed",
        status="active",
        campus_id=None,
    )

    repository.validate_registered_source(write, exact)
    mismatches = (
        exact._replace(source_id="lever"),
        exact._replace(source_account="ACME-BOARD"),
        exact._replace(schema_version="greenhouse-job-board-v2"),
        exact._replace(permission_basis="employer_authorized"),
        exact._replace(status="disabled"),
        exact._replace(campus_id="bits-goa"),
    )
    for registration in mismatches:
        with pytest.raises(repository.CatalogSourceUnavailable):
            repository.validate_registered_source(write, registration)


def test_source_run_must_bind_source_actor_permission_and_status() -> None:
    repository = persistence_repository()
    write = build_write(
        normalized_greenhouse(),
        principal("connector", "service:greenhouse-connector"),
        source_run_id=uuid4(),
    )
    started = repository.BoundSourceRun(
        source_key=write.source_key,
        actor_subject=write.actor_subject,
        permission_basis=write.normalized.source.permission_basis.value,
        status="started",
    )
    completed = started._replace(status="completed")

    repository.validate_bound_source_run(write, started)
    repository.validate_bound_source_run(write, completed)
    mismatches = (
        started._replace(source_key="greenhouse:sha256:wrong"),
        started._replace(actor_subject="service:different-connector"),
        started._replace(permission_basis="employer_authorized"),
        started._replace(status="failed"),
        started._replace(status="cancelled"),
    )
    for source_run in mismatches:
        with pytest.raises(repository.CatalogSourceRunUnavailable):
            repository.validate_bound_source_run(write, source_run)


def test_same_public_content_across_providers_has_one_job_and_two_receipts() -> None:
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
    greenhouse = normalized_greenhouse()
    lever = normalized_lever()
    first_run = uuid4()
    second_run = uuid4()

    async def invoke() -> tuple[Any, Any]:
        first = await service.persist_normalized_jd(
            principal("connector", "service:greenhouse-connector"),
            greenhouse,
            repository,
            receipt_id=uuid4(),
            source_run_id=first_run,
        )
        second = await service.persist_normalized_jd(
            principal("connector", "service:lever-connector"),
            lever,
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
    assert [receipt.source_id for receipt in repository.receipts] == [
        "greenhouse",
        "lever",
    ]
    assert [receipt.source_run_id for receipt in repository.receipts] == [
        first_run,
        second_run,
    ]
    assert [receipt.application_url for receipt in repository.receipts] == [
        "https://boards.greenhouse.io/acme/jobs/1234567",
        "https://jobs.lever.co/acme/lever-posting-42",
    ]
    assert repository.receipts[0].published_at != repository.receipts[1].published_at
    assert (
        repository.receipts[0].application_deadline != repository.receipts[1].application_deadline
    )
    provenance_fields = {field.name for field in fields(repository.receipts[0])}
    assert {
        "receipt_id",
        "source_run_id",
        "source_id",
        "source_locator_fingerprint",
        "permission_basis",
        "schema_version",
        "verification",
        "application_url",
        "published_at",
        "application_deadline",
        "observed_at",
    } <= provenance_fields
    assert not {"authorization_ref", "authorization_reference"} & provenance_fields


def test_postgres_dml_partial_conflict_predicates_are_literal() -> None:
    repository = persistence_repository()
    private_write = build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
    )
    campus_write = build_write(
        normalized_payload(
            sourceId="campus_authorized",
            permissionBasis="placement_cell_authorized",
            sourceAccount="bits-si-2026",
            externalId="SI-42",
            authorizationRef="encrypted-outside-normalized-output",
        ),
        principal("campus_curator", "authjs:curator", campus_id="bits-pilani"),
        source_run_id=uuid4(),
    )
    public_write = build_write(
        normalized_greenhouse(),
        principal("connector", "service:greenhouse-connector"),
        source_run_id=uuid4(),
    )

    for write, access_level in (
        (private_write, "user_private"),
        (campus_write, "campus_restricted"),
        (public_write, "public"),
    ):
        compiled = repository.build_job_upsert(write, uuid4()).compile(dialect=postgresql.dialect())
        sql = str(compiled).lower()
        assert f"where access_level = '{access_level}'" in sql
        assert not {
            key: value for key, value in compiled.params.items() if key.startswith("access_level_")
        }


def test_postgres_public_conflict_target_is_global_content_identity() -> None:
    repository = persistence_repository()
    write = build_write(
        normalized_greenhouse(),
        principal("connector", "service:greenhouse-connector"),
        source_run_id=uuid4(),
    )

    sql = str(
        repository.build_job_upsert(write, uuid4()).compile(dialect=postgresql.dialect())
    ).lower()

    assert "on conflict (catalog_eligibility, fingerprint_version, content_fingerprint)" in sql
    assert "source_locator_fingerprint" not in sql.split("on conflict", maxsplit=1)[1]


def test_provenance_insert_returns_receipt_for_replay_validation() -> None:
    repository = persistence_repository()
    write = build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
    )

    sql = str(
        repository.build_provenance_insert(write, uuid4()).compile(dialect=postgresql.dialect())
    ).lower()

    assert "on conflict (receipt_id) do nothing" in sql
    assert "returning career_catalog.jd_provenance.receipt_id" in sql


def test_exact_receipt_replay_is_verified_and_idempotent() -> None:
    repository_module = persistence_repository()
    write = build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
        receipt_id=uuid4(),
    )
    job_id = uuid4()
    session = ReplaySession(job_id, stored_receipt(write, job_id))
    repository = repository_module.PostgresCatalogRepository(ReplaySessionFactory(session))

    async def invoke() -> Any:
        return await repository.persist(write)

    result = run(invoke)

    assert result.job_description_id == job_id
    assert result.disposition is repository_module.PersistDisposition.DEDUPLICATED
    assert session.provenance_lookup_count == 1


def test_receipt_id_replay_with_different_evidence_is_rejected() -> None:
    repository_module = persistence_repository()
    write = build_write(
        normalized_payload(),
        principal("authenticated_user", "authjs:user-a"),
        receipt_id=uuid4(),
    )
    job_id = uuid4()
    mismatched = stored_receipt(
        write,
        job_id,
        snapshot_fingerprint=f"sha256:{'0' * 64}",
    )
    session = ReplaySession(job_id, mismatched)
    repository = repository_module.PostgresCatalogRepository(ReplaySessionFactory(session))

    async def invoke() -> None:
        await repository.persist(write)

    with pytest.raises(repository_module.CatalogPersistenceConflict):
        run(invoke)
    assert session.provenance_lookup_count == 1


def test_alembic_default_cli_renders_postgresql_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "ALEMBIC_DATABASE_URL",
        "DATABASE_URL",
        "GRADPATH_API_DATABASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    output = io.StringIO()
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output)

    command.upgrade(config, "head", sql=True)

    assert "create schema if not exists career_catalog" in output.getvalue().lower()


def test_alembic_upgrade_renders_isolated_least_privilege_ddl() -> None:
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
        "uq_job_descriptions_public_exact",
    ):
        assert f"create unique index {index}" in sql
    assert "enable row level security" in sql
    assert "force row level security" in sql
    assert "prevent_job_description_mutation" in sql
    assert "prevent_provenance_mutation" in sql
    assert "references public.users" not in sql
    assert "alter table public." not in sql
    assert "ck_catalog_sources_ck_catalog_sources" not in sql
    for table in (
        "catalog_sources",
        "source_runs",
        "job_descriptions",
        "jd_provenance",
    ):
        assert f"alter table career_catalog.{table} enable row level security" in sql
        assert f"alter table career_catalog.{table} force row level security" in sql
    for revocation in (
        "revoke all on schema career_catalog from public",
        "revoke all on all tables in schema career_catalog from public",
        "revoke all on all sequences in schema career_catalog from public",
        "revoke all on all functions in schema career_catalog from public",
        "alter default privileges in schema career_catalog revoke all on tables from public",
        "alter default privileges in schema career_catalog revoke all on sequences from public",
        "alter default privileges in schema career_catalog revoke execute on functions from public",
    ):
        assert revocation in sql
    assert "gradpath_api_runtime" in sql
    assert "not rolbypassrls" in sql
    assert "not rolcanlogin" in sql
    assert "grant select, insert on career_catalog.job_descriptions" in sql
    assert "grant select, insert on career_catalog.jd_provenance" in sql
    source_grant = sql.split("grant select (", maxsplit=1)[1].split(
        ") on career_catalog.catalog_sources",
        maxsplit=1,
    )[0]
    assert "authorization_reference_ciphertext" not in source_grant
    assert "authorization_key_id" not in source_grant
    assert "create role" not in sql


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
