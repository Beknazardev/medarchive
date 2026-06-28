"""add source provenance fields

Revision ID: 20260626_0002
Revises: 20260617_0001
Create Date: 2026-06-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260626_0002"
down_revision = "20260617_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("data_sources", sa.Column("public_url", sa.Text(), nullable=True))
    op.add_column("data_sources", sa.Column("robots_policy_notes", sa.Text(), nullable=True))
    op.add_column("data_sources", sa.Column("crawl_delay_seconds", sa.Integer(), nullable=True))

    op.add_column("clinic_service_prices", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "clinic_service_prices",
        sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.execute("UPDATE clinic_service_prices SET parsed_at = last_seen_at WHERE parsed_at IS NULL")
    op.alter_column("clinic_service_prices", "parsed_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_index("ix_clinic_service_prices_parsed_at", "clinic_service_prices", ["parsed_at"])

    op.add_column("price_history", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "price_history",
        sa.Column("parsed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.execute("UPDATE price_history SET parsed_at = changed_at WHERE parsed_at IS NULL")
    op.alter_column("price_history", "parsed_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_index("ix_price_history_parsed_at", "price_history", ["parsed_at"])


def downgrade() -> None:
    op.drop_index("ix_price_history_parsed_at", table_name="price_history")
    op.drop_column("price_history", "parsed_at")
    op.drop_column("price_history", "source_url")

    op.drop_index("ix_clinic_service_prices_parsed_at", table_name="clinic_service_prices")
    op.drop_column("clinic_service_prices", "parsed_at")
    op.drop_column("clinic_service_prices", "source_url")

    op.drop_column("data_sources", "crawl_delay_seconds")
    op.drop_column("data_sources", "robots_policy_notes")
    op.drop_column("data_sources", "public_url")
