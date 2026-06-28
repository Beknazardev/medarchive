"""add parser audit tables

Revision ID: 20260626_0003
Revises: 20260626_0002
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260626_0003"
down_revision = "20260626_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parser_runs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_snapshot_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parser_runs_data_source_id", "parser_runs", ["data_source_id"])
    op.create_index("ix_parser_runs_parsed_at", "parser_runs", ["parsed_at"])
    op.create_index("ix_parser_runs_started_at", "parser_runs", ["started_at"])
    op.create_index("ix_parser_runs_status", "parser_runs", ["status"])

    op.add_column("import_batches", sa.Column("parser_run_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_import_batches_parser_run_id_parser_runs",
        "import_batches",
        "parser_runs",
        ["parser_run_id"],
        ["id"],
    )
    op.create_index("ix_import_batches_parser_run_id", "import_batches", ["parser_run_id"])

    op.create_table(
        "parser_errors",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("parser_run_id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="error", nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_item", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["parser_run_id"], ["parser_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parser_errors_code", "parser_errors", ["code"])
    op.create_index("ix_parser_errors_created_at", "parser_errors", ["created_at"])
    op.create_index("ix_parser_errors_data_source_id", "parser_errors", ["data_source_id"])
    op.create_index("ix_parser_errors_parser_run_id", "parser_errors", ["parser_run_id"])

    op.create_table(
        "raw_source_snapshots",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("parser_run_id", sa.BigInteger(), nullable=True),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("checksum", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["parser_run_id"], ["parser_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_source_snapshots_captured_at", "raw_source_snapshots", ["captured_at"])
    op.create_index("ix_raw_source_snapshots_data_source_id", "raw_source_snapshots", ["data_source_id"])
    op.create_index("ix_raw_source_snapshots_parser_run_id", "raw_source_snapshots", ["parser_run_id"])
    op.create_index("ix_raw_source_snapshots_retention_until", "raw_source_snapshots", ["retention_until"])

    op.create_table(
        "raw_source_rows",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("parser_run_id", sa.BigInteger(), nullable=True),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_item", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("service_id", sa.BigInteger(), nullable=True),
        sa.Column("clinic_service_price_id", sa.BigInteger(), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_service_price_id"], ["clinic_service_prices.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["parser_run_id"], ["parser_runs.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["snapshot_id"], ["raw_source_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_source_rows_clinic_service_price_id", "raw_source_rows", ["clinic_service_price_id"])
    op.create_index("ix_raw_source_rows_data_source_id", "raw_source_rows", ["data_source_id"])
    op.create_index("ix_raw_source_rows_import_batch_id", "raw_source_rows", ["import_batch_id"])
    op.create_index("ix_raw_source_rows_parser_run_id", "raw_source_rows", ["parser_run_id"])
    op.create_index("ix_raw_source_rows_retention_until", "raw_source_rows", ["retention_until"])
    op.create_index("ix_raw_source_rows_service_id", "raw_source_rows", ["service_id"])
    op.create_index("ix_raw_source_rows_snapshot_id", "raw_source_rows", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_source_rows_snapshot_id", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_service_id", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_retention_until", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_parser_run_id", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_import_batch_id", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_data_source_id", table_name="raw_source_rows")
    op.drop_index("ix_raw_source_rows_clinic_service_price_id", table_name="raw_source_rows")
    op.drop_table("raw_source_rows")

    op.drop_index("ix_raw_source_snapshots_retention_until", table_name="raw_source_snapshots")
    op.drop_index("ix_raw_source_snapshots_parser_run_id", table_name="raw_source_snapshots")
    op.drop_index("ix_raw_source_snapshots_data_source_id", table_name="raw_source_snapshots")
    op.drop_index("ix_raw_source_snapshots_captured_at", table_name="raw_source_snapshots")
    op.drop_table("raw_source_snapshots")

    op.drop_index("ix_parser_errors_parser_run_id", table_name="parser_errors")
    op.drop_index("ix_parser_errors_data_source_id", table_name="parser_errors")
    op.drop_index("ix_parser_errors_created_at", table_name="parser_errors")
    op.drop_index("ix_parser_errors_code", table_name="parser_errors")
    op.drop_table("parser_errors")

    op.drop_index("ix_import_batches_parser_run_id", table_name="import_batches")
    op.drop_constraint("fk_import_batches_parser_run_id_parser_runs", "import_batches", type_="foreignkey")
    op.drop_column("import_batches", "parser_run_id")

    op.drop_index("ix_parser_runs_status", table_name="parser_runs")
    op.drop_index("ix_parser_runs_started_at", table_name="parser_runs")
    op.drop_index("ix_parser_runs_parsed_at", table_name="parser_runs")
    op.drop_index("ix_parser_runs_data_source_id", table_name="parser_runs")
    op.drop_table("parser_runs")
