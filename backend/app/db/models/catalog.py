from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

FINGERPRINT_PATTERN = r"^sha256:[0-9a-f]{64}$"


class CatalogSource(Base):
    __tablename__ = "catalog_sources"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="status_values",
        ),
        CheckConstraint(
            "((authorization_reference_ciphertext IS NULL AND authorization_key_id IS NULL) "
            "OR (authorization_reference_ciphertext IS NOT NULL AND "
            "authorization_key_id IS NOT NULL))",
            name="authorization_cipher_pair",
        ),
        CheckConstraint(
            "(source_id <> 'campus_authorized' OR (campus_id IS NOT NULL AND "
            "authorization_reference_ciphertext IS NOT NULL))",
            name="campus_authorization",
        ),
        CheckConstraint(
            "((source_id = 'user_upload' AND source_key = 'user_upload' AND "
            "source_account IS NULL AND campus_id IS NULL AND schema_version = 'manual-v1' "
            "AND permission_basis = 'user_provided') OR "
            "(source_id = 'campus_authorized' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NOT NULL AND "
            "schema_version = 'campus-import-v1' AND "
            "permission_basis = 'placement_cell_authorized') OR "
            "(source_id = 'synthetic_practice' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NULL AND "
            "schema_version = 'synthetic-v1' AND permission_basis = 'internal_practice') OR "
            "(source_id = 'greenhouse' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NULL AND "
            "schema_version = 'greenhouse-job-board-v1' AND permission_basis IN "
            "('employer_authorized', 'public_api_terms_reviewed')) OR "
            "(source_id = 'lever' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NULL AND "
            "schema_version = 'lever-postings-v0' AND permission_basis IN "
            "('employer_authorized', 'public_api_terms_reviewed')) OR "
            "(source_id = 'ashby' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NULL AND "
            "schema_version = 'ashby-public-posting-v1' AND permission_basis IN "
            "('employer_authorized', 'public_api_terms_reviewed')) OR "
            "(source_id = 'smartrecruiters' AND source_key <> 'user_upload' AND "
            "source_account IS NOT NULL AND campus_id IS NULL AND "
            "schema_version = 'smartrecruiters-posting-v1' AND permission_basis IN "
            "('employer_authorized', 'public_api_terms_reviewed')))",
            name="source_contract",
        ),
        CheckConstraint(
            "((source_id = 'user_upload' AND source_key = 'user_upload') OR "
            "(source_id <> 'user_upload' AND source_key ~ "
            "('^' || source_id || ':sha256:[0-9a-f]{64}$')))",
            name="source_key",
        ),
        UniqueConstraint(
            "source_key",
            "source_id",
            "schema_version",
            name="uq_catalog_sources_source_identity",
        ),
        UniqueConstraint(
            "source_key",
            "source_id",
            "schema_version",
            "permission_basis",
            name="uq_catalog_sources_source_provenance",
        ),
        UniqueConstraint(
            "source_key",
            "permission_basis",
            name="uq_catalog_sources_source_permission",
        ),
        UniqueConstraint(
            "source_key",
            "source_account",
            name="uq_catalog_sources_source_account",
        ),
        UniqueConstraint(
            "source_key",
            "campus_id",
            name="uq_catalog_sources_source_campus",
        ),
    )

    source_key: Mapped[str] = mapped_column(String(320), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40), nullable=False)
    source_account: Mapped[str | None] = mapped_column(String(200))
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_basis: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    campus_id: Mapped[str | None] = mapped_column(String(160))
    canonical_base_url: Mapped[str | None] = mapped_column(Text)
    authorization_reference_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    authorization_key_id: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SourceRun(Base):
    __tablename__ = "source_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'cancelled')",
            name="status_values",
        ),
        CheckConstraint(
            "records_seen >= 0 AND records_written >= 0",
            name="record_counts_nonnegative",
        ),
        Index("ix_source_runs_source_started", "source_key", "started_at"),
        ForeignKeyConstraint(
            ("source_key", "permission_basis"),
            (
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.permission_basis",
            ),
            name="fk_source_runs_source_registration",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "source_key",
            "permission_basis",
            "actor_subject",
            name="uq_source_runs_provenance_binding",
        ),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(320), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_basis: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    source_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        CheckConstraint(
            "((access_level = 'user_private' AND owner_subject IS NOT NULL AND "
            "campus_id IS NULL AND catalog_eligibility = 'private_analysis_only') OR "
            "(access_level = 'campus_restricted' AND campus_id IS NOT NULL AND "
            "owner_subject IS NULL AND catalog_eligibility = 'campus_catalog') OR "
            "(access_level = 'public' AND owner_subject IS NULL AND campus_id IS NULL "
            "AND source_account IS NOT NULL AND catalog_eligibility IN "
            "('public_catalog', 'practice_only')))",
            name="scope",
        ),
        CheckConstraint(
            "((verification = 'synthetic_practice') = (catalog_eligibility = 'practice_only'))",
            name="synthetic_eligibility",
        ),
        CheckConstraint(
            "((source_id = 'user_upload' AND access_level = 'user_private' AND "
            "source_account IS NULL AND verification = 'user_asserted' AND "
            "catalog_eligibility = 'private_analysis_only') OR "
            "(source_id = 'campus_authorized' AND access_level = 'campus_restricted' AND "
            "source_account IS NOT NULL AND verification = 'campus_authorized' AND "
            "catalog_eligibility = 'campus_catalog') OR "
            "(source_id = 'synthetic_practice' AND access_level = 'public' AND "
            "source_account IS NOT NULL AND verification = 'synthetic_practice' AND "
            "catalog_eligibility = 'practice_only') OR "
            "(source_id IN ('greenhouse', 'lever', 'ashby', 'smartrecruiters') AND "
            "access_level = 'public' AND source_account IS NOT NULL AND "
            "verification = 'provider_record' AND "
            "catalog_eligibility = 'public_catalog'))",
            name="source_verification",
        ),
        CheckConstraint(
            "content_fingerprint ~ '^sha256:[0-9a-f]{64}$' AND "
            "source_locator_fingerprint ~ '^sha256:[0-9a-f]{64}$'",
            name="fingerprints",
        ),
        Index(
            "uq_job_descriptions_private_exact",
            "owner_subject",
            "fingerprint_version",
            "content_fingerprint",
            unique=True,
            postgresql_where=text("access_level = 'user_private'"),
        ),
        Index(
            "uq_job_descriptions_campus_exact",
            "campus_id",
            "fingerprint_version",
            "content_fingerprint",
            unique=True,
            postgresql_where=text("access_level = 'campus_restricted'"),
        ),
        Index(
            "uq_job_descriptions_public_exact",
            "catalog_eligibility",
            "fingerprint_version",
            "content_fingerprint",
            unique=True,
            postgresql_where=text("access_level = 'public'"),
        ),
        ForeignKeyConstraint(
            ("source_key", "source_id", "schema_version"),
            (
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_id",
                "career_catalog.catalog_sources.schema_version",
            ),
            name="fk_job_descriptions_source_identity",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("source_key", "source_account"),
            (
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_account",
            ),
            name="fk_job_descriptions_source_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("source_key", "campus_id"),
            (
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.campus_id",
            ),
            name="fk_job_descriptions_source_campus",
            ondelete="RESTRICT",
        ),
        Index("ix_job_descriptions_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(320), nullable=False)
    source_id: Mapped[str] = mapped_column(String(40), nullable=False)
    source_account: Mapped[str | None] = mapped_column(String(200))
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_locator_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    access_level: Mapped[str] = mapped_column(String(40), nullable=False)
    catalog_eligibility: Mapped[str] = mapped_column(String(40), nullable=False)
    verification: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_subject: Mapped[str | None] = mapped_column(String(320))
    campus_id: Mapped[str | None] = mapped_column(String(160))
    organization: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    tracks: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    opportunity_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    application_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    fingerprint_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JDProvenance(Base):
    __tablename__ = "jd_provenance"
    __table_args__ = (
        CheckConstraint(
            "source_locator_fingerprint ~ '^sha256:[0-9a-f]{64}$' AND "
            "snapshot_fingerprint ~ '^sha256:[0-9a-f]{64}$'",
            name="fingerprints",
        ),
        CheckConstraint(
            "((source_id = 'user_upload' AND source_run_id IS NULL AND "
            "permission_basis = 'user_provided' AND verification = 'user_asserted') OR "
            "(source_id = 'campus_authorized' AND source_run_id IS NOT NULL AND "
            "permission_basis = 'placement_cell_authorized' AND "
            "verification = 'campus_authorized') OR "
            "(source_id = 'synthetic_practice' AND source_run_id IS NOT NULL AND "
            "permission_basis = 'internal_practice' AND "
            "verification = 'synthetic_practice' AND source_url IS NULL AND "
            "application_url IS NULL AND published_at IS NULL AND "
            "application_deadline IS NULL) OR "
            "(source_id IN ('greenhouse', 'lever', 'ashby', 'smartrecruiters') AND "
            "source_run_id IS NOT NULL AND permission_basis IN "
            "('employer_authorized', 'public_api_terms_reviewed') AND "
            "verification = 'provider_record'))",
            name="source_provenance",
        ),
        CheckConstraint(
            "(published_at IS NULL OR application_deadline IS NULL OR "
            "application_deadline >= published_at)",
            name="listing_dates",
        ),
        Index("ix_jd_provenance_job", "job_description_id", "captured_at"),
        ForeignKeyConstraint(
            ("source_key", "source_id", "schema_version", "permission_basis"),
            (
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_id",
                "career_catalog.catalog_sources.schema_version",
                "career_catalog.catalog_sources.permission_basis",
            ),
            name="fk_jd_provenance_source_registration",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ("source_run_id", "source_key", "permission_basis", "imported_by_subject"),
            (
                "career_catalog.source_runs.id",
                "career_catalog.source_runs.source_key",
                "career_catalog.source_runs.permission_basis",
                "career_catalog.source_runs.actor_subject",
            ),
            name="fk_jd_provenance_source_run_binding",
            ondelete="RESTRICT",
        ),
    )

    receipt_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    job_description_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("career_catalog.job_descriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_key: Mapped[str] = mapped_column(String(320), nullable=False)
    source_run_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    source_id: Mapped[str] = mapped_column(String(40), nullable=False)
    source_locator_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    snapshot_fingerprint: Mapped[str] = mapped_column(String(71), nullable=False)
    permission_basis: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    verification: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_by_subject: Mapped[str] = mapped_column(String(320), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
