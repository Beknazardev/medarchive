"""add unmatched service queue

Revision ID: 20260626_0004
Revises: 20260626_0003
Create Date: 2026-06-26 00:04:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260626_0004"
down_revision: str | None = "20260626_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column(
            "normalization_status",
            sa.String(length=50),
            nullable=False,
            server_default="fallback",
        ),
    )
    op.add_column(
        "services",
        sa.Column(
            "normalization_confidence",
            sa.Numeric(4, 3),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "unmatched_service_records",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("service_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_source_row_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_category", sa.String(length=255), nullable=False),
        sa.Column("raw_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_raw_category", sa.String(length=255), nullable=False),
        sa.Column("normalized_raw_name", sa.String(length=255), nullable=False),
        sa.Column("suggested_normalized_service_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="open", nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), server_default="0", nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_item", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["raw_source_row_id"], ["raw_source_rows.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["suggested_normalized_service_id"], ["normalized_services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_unmatched_service_records_status",
        "unmatched_service_records",
        ["status"],
    )
    op.create_index(
        "ix_unmatched_service_records_service_id",
        "unmatched_service_records",
        ["service_id"],
    )
    op.create_index(
        "ix_unmatched_service_records_data_source_id",
        "unmatched_service_records",
        ["data_source_id"],
    )
    op.create_index(
        "ix_unmatched_service_records_normalized_raw",
        "unmatched_service_records",
        ["normalized_raw_category", "normalized_raw_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_unmatched_service_records_normalized_raw", table_name="unmatched_service_records")
    op.drop_index("ix_unmatched_service_records_data_source_id", table_name="unmatched_service_records")
    op.drop_index("ix_unmatched_service_records_service_id", table_name="unmatched_service_records")
    op.drop_index("ix_unmatched_service_records_status", table_name="unmatched_service_records")
    op.drop_table("unmatched_service_records")
    op.drop_column("services", "normalization_confidence")
    op.drop_column("services", "normalization_status")
