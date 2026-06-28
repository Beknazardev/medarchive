"""add localized service and category names

Revision ID: 20260628_0006
Revises: 20260627_0005
Create Date: 2026-06-28 00:06:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260628_0006"
down_revision: str | None = "20260627_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NormalizedService - localized names
    op.add_column("normalized_services", sa.Column("name_ru", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("name_kk", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("name_en", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("category_ru", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("category_kk", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("category_en", sa.String(length=255), nullable=True))
    op.add_column("normalized_services", sa.Column("canonical_key", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_normalized_services_canonical_key", "normalized_services", ["canonical_key"])

    # ServiceCategory - localized names
    op.add_column("service_categories", sa.Column("name_ru", sa.String(length=255), nullable=True))
    op.add_column("service_categories", sa.Column("name_kk", sa.String(length=255), nullable=True))
    op.add_column("service_categories", sa.Column("name_en", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_constraint("uq_normalized_services_canonical_key", "normalized_services", type_="unique")
    op.drop_column("normalized_services", "canonical_key")
    op.drop_column("normalized_services", "category_en")
    op.drop_column("normalized_services", "category_kk")
    op.drop_column("normalized_services", "category_ru")
    op.drop_column("normalized_services", "name_en")
    op.drop_column("normalized_services", "name_kk")
    op.drop_column("normalized_services", "name_ru")

    op.drop_column("service_categories", "name_en")
    op.drop_column("service_categories", "name_kk")
    op.drop_column("service_categories", "name_ru")
