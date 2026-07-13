from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "career_catalog"


def upgrade() -> None:
    op.create_table(
        "catalog_sources",
        sa.Column("source_key", sa.String(length=320), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("source_account", sa.String(length=200), nullable=True),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("permission_basis", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("campus_id", sa.String(length=160), nullable=True),
        sa.Column("canonical_base_url", sa.Text(), nullable=True),
        sa.Column("authorization_reference_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("authorization_key_id", sa.String(length=160), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name=op.f("ck_catalog_sources_status_values"),
        ),
        sa.CheckConstraint(
            "((authorization_reference_ciphertext IS NULL AND authorization_key_id IS NULL) "
            "OR (authorization_reference_ciphertext IS NOT NULL AND "
            "authorization_key_id IS NOT NULL))",
            name=op.f("ck_catalog_sources_authorization_cipher_pair"),
        ),
        sa.CheckConstraint(
            "(source_id <> 'campus_authorized' OR (campus_id IS NOT NULL AND "
            "authorization_reference_ciphertext IS NOT NULL))",
            name=op.f("ck_catalog_sources_campus_authorization"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_catalog_sources_source_contract"),
        ),
        sa.CheckConstraint(
            "((source_id = 'user_upload' AND source_key = 'user_upload') OR "
            "(source_id <> 'user_upload' AND source_key ~ "
            "('^' || source_id || ':sha256:[0-9a-f]{64}$')))",
            name=op.f("ck_catalog_sources_source_key"),
        ),
        sa.PrimaryKeyConstraint("source_key", name="pk_catalog_sources"),
        sa.UniqueConstraint(
            "source_key",
            "source_id",
            "schema_version",
            name="uq_catalog_sources_source_identity",
        ),
        sa.UniqueConstraint(
            "source_key",
            "source_id",
            "schema_version",
            "permission_basis",
            name="uq_catalog_sources_source_provenance",
        ),
        sa.UniqueConstraint(
            "source_key",
            "permission_basis",
            name="uq_catalog_sources_source_permission",
        ),
        sa.UniqueConstraint(
            "source_key",
            "source_account",
            name="uq_catalog_sources_source_account",
        ),
        sa.UniqueConstraint(
            "source_key",
            "campus_id",
            name="uq_catalog_sources_source_campus",
        ),
        schema=SCHEMA,
    )
    op.execute(
        "INSERT INTO career_catalog.catalog_sources "
        "(source_key, source_id, schema_version, permission_basis, status) VALUES "
        "('user_upload', 'user_upload', 'manual-v1', 'user_provided', 'active') "
        "ON CONFLICT (source_key) DO NOTHING"
    )

    op.create_table(
        "source_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_key", sa.String(length=320), nullable=False),
        sa.Column("adapter_version", sa.String(length=100), nullable=False),
        sa.Column("permission_basis", sa.String(length=60), nullable=False),
        sa.Column("actor_subject", sa.String(length=320), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=False),
        sa.Column("records_written", sa.Integer(), nullable=False),
        sa.Column("cursor_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_source_runs_status_values"),
        ),
        sa.CheckConstraint(
            "records_seen >= 0 AND records_written >= 0",
            name=op.f("ck_source_runs_record_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["source_key", "permission_basis"],
            [
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.permission_basis",
            ],
            name="fk_source_runs_source_registration",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_runs"),
        sa.UniqueConstraint(
            "id",
            "source_key",
            "permission_basis",
            "actor_subject",
            name="uq_source_runs_provenance_binding",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_source_runs_source_started",
        "source_runs",
        ["source_key", "started_at"],
        schema=SCHEMA,
    )

    op.create_table(
        "job_descriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_key", sa.String(length=320), nullable=False),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("source_account", sa.String(length=200), nullable=True),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("source_locator_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("access_level", sa.String(length=40), nullable=False),
        sa.Column("catalog_eligibility", sa.String(length=40), nullable=False),
        sa.Column("verification", sa.String(length=40), nullable=False),
        sa.Column("owner_subject", sa.String(length=320), nullable=True),
        sa.Column("campus_id", sa.String(length=160), nullable=True),
        sa.Column("organization", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("tracks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("opportunity_kind", sa.String(length=40), nullable=False),
        sa.Column("application_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("fingerprint_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "((access_level = 'user_private' AND owner_subject IS NOT NULL AND "
            "campus_id IS NULL AND catalog_eligibility = 'private_analysis_only') OR "
            "(access_level = 'campus_restricted' AND campus_id IS NOT NULL AND "
            "owner_subject IS NULL AND catalog_eligibility = 'campus_catalog') OR "
            "(access_level = 'public' AND owner_subject IS NULL AND campus_id IS NULL "
            "AND source_account IS NOT NULL AND catalog_eligibility IN "
            "('public_catalog', 'practice_only')))",
            name=op.f("ck_job_descriptions_scope"),
        ),
        sa.CheckConstraint(
            "((verification = 'synthetic_practice') = (catalog_eligibility = 'practice_only'))",
            name=op.f("ck_job_descriptions_synthetic_eligibility"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_job_descriptions_source_verification"),
        ),
        sa.CheckConstraint(
            "content_fingerprint ~ '^sha256:[0-9a-f]{64}$' AND "
            "source_locator_fingerprint ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_job_descriptions_fingerprints"),
        ),
        sa.ForeignKeyConstraint(
            ["source_key", "source_id", "schema_version"],
            [
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_id",
                "career_catalog.catalog_sources.schema_version",
            ],
            name="fk_job_descriptions_source_identity",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_key", "source_account"],
            [
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_account",
            ],
            name="fk_job_descriptions_source_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_key", "campus_id"],
            [
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.campus_id",
            ],
            name="fk_job_descriptions_source_campus",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_job_descriptions"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_job_descriptions_created_at",
        "job_descriptions",
        ["created_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_job_descriptions_private_exact",
        "job_descriptions",
        ["owner_subject", "fingerprint_version", "content_fingerprint"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("access_level = 'user_private'"),
    )
    op.create_index(
        "uq_job_descriptions_campus_exact",
        "job_descriptions",
        ["campus_id", "fingerprint_version", "content_fingerprint"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("access_level = 'campus_restricted'"),
    )
    op.create_index(
        "uq_job_descriptions_public_exact",
        "job_descriptions",
        ["catalog_eligibility", "fingerprint_version", "content_fingerprint"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("access_level = 'public'"),
    )

    op.create_table(
        "jd_provenance",
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_description_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_key", sa.String(length=320), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", sa.String(length=40), nullable=False),
        sa.Column("source_locator_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("snapshot_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("permission_basis", sa.String(length=60), nullable=False),
        sa.Column("schema_version", sa.String(length=100), nullable=False),
        sa.Column("verification", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=300), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("application_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("application_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_by_subject", sa.String(length=320), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_locator_fingerprint ~ '^sha256:[0-9a-f]{64}$' AND "
            "snapshot_fingerprint ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_jd_provenance_fingerprints"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_jd_provenance_source_provenance"),
        ),
        sa.CheckConstraint(
            "(published_at IS NULL OR application_deadline IS NULL OR "
            "application_deadline >= published_at)",
            name=op.f("ck_jd_provenance_listing_dates"),
        ),
        sa.ForeignKeyConstraint(
            ["job_description_id"],
            ["career_catalog.job_descriptions.id"],
            name="fk_jd_provenance_job_description_id_job_descriptions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_key", "source_id", "schema_version", "permission_basis"],
            [
                "career_catalog.catalog_sources.source_key",
                "career_catalog.catalog_sources.source_id",
                "career_catalog.catalog_sources.schema_version",
                "career_catalog.catalog_sources.permission_basis",
            ],
            name="fk_jd_provenance_source_registration",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id", "source_key", "permission_basis", "imported_by_subject"],
            [
                "career_catalog.source_runs.id",
                "career_catalog.source_runs.source_key",
                "career_catalog.source_runs.permission_basis",
                "career_catalog.source_runs.actor_subject",
            ],
            name="fk_jd_provenance_source_run_binding",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("receipt_id", name="pk_jd_provenance"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_jd_provenance_job",
        "jd_provenance",
        ["job_description_id", "captured_at"],
        schema=SCHEMA,
    )

    for table_name in (
        "catalog_sources",
        "source_runs",
        "job_descriptions",
        "jd_provenance",
    ):
        op.execute(f"ALTER TABLE career_catalog.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE career_catalog.{table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY catalog_sources_read_scope
        ON career_catalog.catalog_sources
        FOR SELECT
        USING (
            (source_id = 'user_upload'
                AND current_setting('app.actor_kind', true) = 'authenticated_user')
            OR (source_id = 'campus_authorized'
                AND current_setting('app.actor_kind', true) IN ('campus_curator', 'admin')
                AND campus_id = NULLIF(current_setting('app.campus_id', true), ''))
            OR (source_id = 'synthetic_practice'
                AND current_setting('app.actor_kind', true) = 'admin')
            OR (source_id IN ('greenhouse', 'lever', 'ashby', 'smartrecruiters')
                AND current_setting('app.actor_kind', true) IN ('connector', 'admin'))
        )
        """
    )
    op.execute(
        """
        CREATE POLICY source_runs_read_scope
        ON career_catalog.source_runs
        FOR SELECT
        USING (
            actor_subject = NULLIF(current_setting('app.actor_subject', true), '')
            AND EXISTS (
                SELECT 1 FROM career_catalog.catalog_sources AS source
                WHERE source.source_key = source_runs.source_key
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY job_descriptions_read_scope
        ON career_catalog.job_descriptions
        FOR SELECT
        USING (
            access_level = 'public'
            OR (access_level = 'user_private' AND owner_subject =
                NULLIF(current_setting('app.owner_subject', true), ''))
            OR (access_level = 'campus_restricted' AND campus_id =
                NULLIF(current_setting('app.campus_id', true), ''))
        )
        """
    )
    op.execute(
        """
        CREATE POLICY job_descriptions_insert_scope
        ON career_catalog.job_descriptions
        FOR INSERT
        WITH CHECK (
            (access_level = 'user_private'
                AND current_setting('app.actor_kind', true) = 'authenticated_user'
                AND owner_subject = NULLIF(current_setting('app.owner_subject', true), ''))
            OR (access_level = 'campus_restricted'
                AND current_setting('app.actor_kind', true) IN ('campus_curator', 'admin')
                AND campus_id = NULLIF(current_setting('app.campus_id', true), ''))
            OR (access_level = 'public'
                AND ((catalog_eligibility = 'practice_only'
                        AND current_setting('app.actor_kind', true) = 'admin')
                    OR (catalog_eligibility = 'public_catalog'
                        AND current_setting('app.actor_kind', true) IN ('connector', 'admin'))))
        )
        """
    )
    op.execute(
        """
        CREATE POLICY jd_provenance_read_scope
        ON career_catalog.jd_provenance
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM career_catalog.job_descriptions AS jd
                WHERE jd.id = jd_provenance.job_description_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY jd_provenance_insert_scope
        ON career_catalog.jd_provenance
        FOR INSERT
        WITH CHECK (
            imported_by_subject = NULLIF(current_setting('app.actor_subject', true), '')
            AND EXISTS (
                SELECT 1 FROM career_catalog.job_descriptions AS jd
                WHERE jd.id = jd_provenance.job_description_id
            )
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION career_catalog.reject_immutable_catalog_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'catalog content and provenance are append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_job_description_mutation
        BEFORE UPDATE OR DELETE ON career_catalog.job_descriptions
        FOR EACH ROW EXECUTE FUNCTION career_catalog.reject_immutable_catalog_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER prevent_provenance_mutation
        BEFORE UPDATE OR DELETE ON career_catalog.jd_provenance
        FOR EACH ROW EXECUTE FUNCTION career_catalog.reject_immutable_catalog_mutation()
        """
    )
    op.execute("REVOKE ALL ON SCHEMA career_catalog FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA career_catalog FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA career_catalog FROM PUBLIC")
    op.execute("REVOKE ALL ON ALL FUNCTIONS IN SCHEMA career_catalog FROM PUBLIC")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA career_catalog REVOKE ALL ON TABLES FROM PUBLIC")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA career_catalog REVOKE ALL ON SEQUENCES FROM PUBLIC"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA career_catalog REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_roles
                WHERE rolname = 'gradpath_api_runtime'
                    AND NOT rolsuper
                    AND NOT rolbypassrls
                    AND NOT rolcanlogin
            ) OR current_user = 'gradpath_api_runtime' THEN
                RAISE EXCEPTION
                    'pre-create gradpath_api_runtime as a NOLOGIN, non-owner, '
                    'non-superuser, non-BYPASSRLS role before applying this migration';
            END IF;
        END;
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA career_catalog TO gradpath_api_runtime")
    op.execute(
        """
        GRANT SELECT (
            source_key,
            source_id,
            source_account,
            schema_version,
            permission_basis,
            status,
            campus_id,
            canonical_base_url,
            created_at,
            updated_at
        ) ON career_catalog.catalog_sources TO gradpath_api_runtime
        """
    )
    op.execute(
        """
        GRANT SELECT (
            id,
            source_key,
            permission_basis,
            actor_subject,
            status
        ) ON career_catalog.source_runs TO gradpath_api_runtime
        """
    )
    op.execute("GRANT SELECT, INSERT ON career_catalog.job_descriptions TO gradpath_api_runtime")
    op.execute("GRANT SELECT, INSERT ON career_catalog.jd_provenance TO gradpath_api_runtime")
    op.execute(
        "GRANT EXECUTE ON FUNCTION career_catalog.reject_immutable_catalog_mutation() "
        "TO gradpath_api_runtime"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_provenance_mutation ON career_catalog.jd_provenance")
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_job_description_mutation ON career_catalog.job_descriptions"
    )
    op.execute("DROP FUNCTION IF EXISTS career_catalog.reject_immutable_catalog_mutation()")
    op.drop_table("jd_provenance", schema=SCHEMA)
    op.drop_table("job_descriptions", schema=SCHEMA)
    op.drop_table("source_runs", schema=SCHEMA)
    op.drop_table("catalog_sources", schema=SCHEMA)
    op.execute("REVOKE USAGE ON SCHEMA career_catalog FROM gradpath_api_runtime")
