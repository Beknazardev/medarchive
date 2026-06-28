"""add ingestion audit metadata and price observations

Revision ID: 20260627_0005
Revises: 20260626_0004
Create Date: 2026-06-27 00:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260627_0005"
down_revision: str | None = "20260626_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "parser_errors",
        sa.Column("stage", sa.String(length=50), server_default="unknown", nullable=False),
    )
    op.add_column(
        "parser_errors",
        sa.Column("retryable", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    op.add_column("raw_source_snapshots", sa.Column("requested_url", sa.Text(), nullable=True))
    op.add_column("raw_source_snapshots", sa.Column("final_url", sa.Text(), nullable=True))
    op.add_column("raw_source_snapshots", sa.Column("http_status", sa.Integer(), nullable=True))
    op.add_column(
        "raw_source_snapshots",
        sa.Column(
            "response_headers",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    op.add_column(
        "raw_source_snapshots",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column("raw_source_snapshots", sa.Column("byte_size", sa.Integer(), nullable=True))
    op.add_column("raw_source_snapshots", sa.Column("storage_uri", sa.Text(), nullable=True))
    op.add_column(
        "raw_source_snapshots",
        sa.Column("source_document_date", sa.Date(), nullable=True),
    )

    op.add_column(
        "raw_source_rows",
        sa.Column("record_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "raw_source_rows",
        sa.Column(
            "extraction_status",
            sa.String(length=50),
            server_default="extracted",
            nullable=False,
        ),
    )
    op.add_column(
        "raw_source_rows",
        sa.Column(
            "validation_status",
            sa.String(length=50),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "raw_source_rows",
        sa.Column(
            "rejection_details",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )
    op.create_index("ix_raw_source_rows_record_hash", "raw_source_rows", ["record_hash"])
    op.create_index(
        "ix_raw_source_rows_validation_status",
        "raw_source_rows",
        ["validation_status"],
    )

    op.add_column(
        "unmatched_service_records",
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column("review_action", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "unmatched_service_records",
        sa.Column("review_note", sa.Text(), nullable=True),
    )

    op.create_table(
        "price_observations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_service_price_id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("normalized_service_id", sa.BigInteger(), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("parser_run_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("source_updated_at", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_detected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["branch_id"], ["clinic_branches.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["clinic_service_price_id"], ["clinic_service_prices.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["normalized_service_id"], ["normalized_services.id"]),
        sa.ForeignKeyConstraint(["parser_run_id"], ["parser_runs.id"]),
        sa.ForeignKeyConstraint(["raw_source_row_id"], ["raw_source_rows.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_price_observations_current_price_id",
        "price_observations",
        ["clinic_service_price_id"],
    )
    op.create_index(
        "ix_price_observations_service_id",
        "price_observations",
        ["service_id"],
    )
    op.create_index(
        "ix_price_observations_normalized_service_id",
        "price_observations",
        ["normalized_service_id"],
    )
    op.create_index(
        "ix_price_observations_import_batch_id",
        "price_observations",
        ["import_batch_id"],
    )
    op.create_index(
        "ix_price_observations_data_source_id",
        "price_observations",
        ["data_source_id"],
    )
    op.create_index(
        "ix_price_observations_parser_run_id",
        "price_observations",
        ["parser_run_id"],
    )
    op.create_index(
        "ix_price_observations_raw_source_row_id",
        "price_observations",
        ["raw_source_row_id"],
    )
    op.create_index(
        "ix_price_observations_observed_at",
        "price_observations",
        ["observed_at"],
    )
    op.create_index(
        "ix_price_observations_parsed_at",
        "price_observations",
        ["parsed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_observations_parsed_at", table_name="price_observations")
    op.drop_index("ix_price_observations_observed_at", table_name="price_observations")
    op.drop_index("ix_price_observations_raw_source_row_id", table_name="price_observations")
    op.drop_index("ix_price_observations_parser_run_id", table_name="price_observations")
    op.drop_index("ix_price_observations_data_source_id", table_name="price_observations")
    op.drop_index("ix_price_observations_import_batch_id", table_name="price_observations")
    op.drop_index(
        "ix_price_observations_normalized_service_id",
        table_name="price_observations",
    )
    op.drop_index("ix_price_observations_service_id", table_name="price_observations")
    op.drop_index("ix_price_observations_current_price_id", table_name="price_observations")
    op.drop_table("price_observations")

    op.drop_column("unmatched_service_records", "review_note")
    op.drop_column("unmatched_service_records", "review_action")
    op.drop_column("unmatched_service_records", "reviewed_by")
    op.drop_column("unmatched_service_records", "reviewed_at")
    op.drop_column("unmatched_service_records", "last_seen_at")
    op.drop_column("unmatched_service_records", "first_seen_at")
    op.drop_column("unmatched_service_records", "occurrence_count")

    op.drop_index("ix_raw_source_rows_validation_status", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_record_hash", table_name="raw_source_rows")
    op.drop_column("raw_source_rows", "rejection_details")
    op.drop_column("raw_source_rows", "validation_status")
    op.drop_column("raw_source_rows", "extraction_status")
    op.drop_column("raw_source_rows", "record_hash")

    op.drop_column("raw_source_snapshots", "source_document_date")
    op.drop_column("raw_source_snapshots", "storage_uri")
    op.drop_column("raw_source_snapshots", "byte_size")
    op.drop_column("raw_source_snapshots", "content_sha256")
    op.drop_column("raw_source_snapshots", "response_headers")
    op.drop_column("raw_source_snapshots", "http_status")
    op.drop_column("raw_source_snapshots", "final_url")
    op.drop_column("raw_source_snapshots", "requested_url")

    op.drop_column("parser_errors", "retryable")
    op.drop_column("parser_errors", "stage")
