"""initial database schema

Revision ID: 20260617_0001
Revises: None
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260617_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "data_sources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_data_sources_type", "data_sources", ["type"])

    op.create_table(
        "service_categories",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("normalized_name"),
    )

    op.create_table(
        "clinics",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("legal_name", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_source_id", "external_id", name="uq_clinics_source_external"),
    )
    op.create_index("ix_clinics_city", "clinics", ["city"])
    op.create_index("ix_clinics_normalized_name", "clinics", ["normalized_name"])
    op.create_index(
        "ix_clinics_name_tsv",
        "clinics",
        [sa.text("to_tsvector('simple', name)")],
        postgresql_using="gin",
    )

    op.create_table(
        "normalized_services",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["service_categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_normalized_services_category_id", "normalized_services", ["category_id"])
    op.create_index("ix_normalized_services_aliases", "normalized_services", ["aliases"], postgresql_using="gin")
    op.create_index(
        "ix_normalized_services_name_tsv",
        "normalized_services",
        [sa.text("to_tsvector('simple', name)")],
        postgresql_using="gin",
    )

    op.create_table(
        "clinic_branches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("normalized_address", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinic_branches_city", "clinic_branches", ["city"])
    op.create_index("ix_clinic_branches_clinic_id", "clinic_branches", ["clinic_id"])
    op.create_index("ix_clinic_branches_normalized_address", "clinic_branches", ["normalized_address"])
    op.create_index(
        "uq_clinic_branches_clinic_external",
        "clinic_branches",
        ["clinic_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("normalized_service_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["service_categories.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["normalized_service_id"], ["normalized_services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_services_category_id", "services", ["category_id"])
    op.create_index("ix_services_normalized_name", "services", ["normalized_name"])
    op.create_index("ix_services_normalized_service_id", "services", ["normalized_service_id"])
    op.create_index(
        "ix_services_name_tsv",
        "services",
        [sa.text("to_tsvector('simple', name)")],
        postgresql_using="gin",
    )
    op.create_index(
        "uq_services_source_external",
        "services",
        ["data_source_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("source_batch_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("received_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"])
    op.create_index("ix_import_batches_data_source_id", "import_batches", ["data_source_id"])
    op.create_index("ix_import_batches_source_batch_id", "import_batches", ["source_batch_id"])
    op.create_index("ix_import_batches_status", "import_batches", ["status"])

    op.create_table(
        "clinic_service_prices",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("normalized_service_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("is_available", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("updated_at", sa.Date(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("system_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["clinic_branches.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["normalized_service_id"], ["normalized_services.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "clinic_id",
            "branch_id",
            "service_id",
            "currency",
            name="uq_clinic_service_prices_current",
        ),
    )
    op.create_index("ix_clinic_service_prices_branch_id", "clinic_service_prices", ["branch_id"])
    op.create_index("ix_clinic_service_prices_clinic_id", "clinic_service_prices", ["clinic_id"])
    op.create_index("ix_clinic_service_prices_currency", "clinic_service_prices", ["currency"])
    op.create_index("ix_clinic_service_prices_normalized_service_id", "clinic_service_prices", ["normalized_service_id"])
    op.create_index("ix_clinic_service_prices_price", "clinic_service_prices", ["price"])
    op.create_index("ix_clinic_service_prices_updated_at", "clinic_service_prices", ["updated_at"])

    op.create_table(
        "import_errors",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("field", sa.String(length=255), nullable=True),
        sa.Column("raw_item", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_errors_code", "import_errors", ["code"])
    op.create_index("ix_import_errors_created_at", "import_errors", ["created_at"])
    op.create_index("ix_import_errors_import_batch_id", "import_errors", ["import_batch_id"])

    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_service_price_id", sa.BigInteger(), nullable=False),
        sa.Column("clinic_id", sa.BigInteger(), nullable=False),
        sa.Column("branch_id", sa.BigInteger(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.Column("old_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("new_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("import_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["clinic_branches.id"]),
        sa.ForeignKeyConstraint(["clinic_id"], ["clinics.id"]),
        sa.ForeignKeyConstraint(["clinic_service_price_id"], ["clinic_service_prices.id"]),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_history_changed_at", "price_history", ["changed_at"])
    op.create_index("ix_price_history_clinic_id", "price_history", ["clinic_id"])
    op.create_index("ix_price_history_clinic_service_price_id", "price_history", ["clinic_service_price_id"])
    op.create_index("ix_price_history_import_batch_id", "price_history", ["import_batch_id"])
    op.create_index("ix_price_history_service_id", "price_history", ["service_id"])


def downgrade() -> None:
    op.drop_index("ix_price_history_service_id", table_name="price_history")
    op.drop_index("ix_price_history_import_batch_id", table_name="price_history")
    op.drop_index("ix_price_history_clinic_service_price_id", table_name="price_history")
    op.drop_index("ix_price_history_clinic_id", table_name="price_history")
    op.drop_index("ix_price_history_changed_at", table_name="price_history")
    op.drop_table("price_history")

    op.drop_index("ix_import_errors_import_batch_id", table_name="import_errors")
    op.drop_index("ix_import_errors_created_at", table_name="import_errors")
    op.drop_index("ix_import_errors_code", table_name="import_errors")
    op.drop_table("import_errors")

    op.drop_index("ix_clinic_service_prices_updated_at", table_name="clinic_service_prices")
    op.drop_index("ix_clinic_service_prices_price", table_name="clinic_service_prices")
    op.drop_index("ix_clinic_service_prices_normalized_service_id", table_name="clinic_service_prices")
    op.drop_index("ix_clinic_service_prices_currency", table_name="clinic_service_prices")
    op.drop_index("ix_clinic_service_prices_clinic_id", table_name="clinic_service_prices")
    op.drop_index("ix_clinic_service_prices_branch_id", table_name="clinic_service_prices")
    op.drop_table("clinic_service_prices")

    op.drop_index("ix_import_batches_status", table_name="import_batches")
    op.drop_index("ix_import_batches_source_batch_id", table_name="import_batches")
    op.drop_index("ix_import_batches_data_source_id", table_name="import_batches")
    op.drop_index("ix_import_batches_created_at", table_name="import_batches")
    op.drop_table("import_batches")

    op.drop_index("uq_services_source_external", table_name="services")
    op.drop_index("ix_services_name_tsv", table_name="services")
    op.drop_index("ix_services_normalized_service_id", table_name="services")
    op.drop_index("ix_services_normalized_name", table_name="services")
    op.drop_index("ix_services_category_id", table_name="services")
    op.drop_table("services")

    op.drop_index("uq_clinic_branches_clinic_external", table_name="clinic_branches")
    op.drop_index("ix_clinic_branches_normalized_address", table_name="clinic_branches")
    op.drop_index("ix_clinic_branches_clinic_id", table_name="clinic_branches")
    op.drop_index("ix_clinic_branches_city", table_name="clinic_branches")
    op.drop_table("clinic_branches")

    op.drop_index("ix_normalized_services_name_tsv", table_name="normalized_services")
    op.drop_index("ix_normalized_services_aliases", table_name="normalized_services")
    op.drop_index("ix_normalized_services_category_id", table_name="normalized_services")
    op.drop_table("normalized_services")

    op.drop_index("ix_clinics_name_tsv", table_name="clinics")
    op.drop_index("ix_clinics_normalized_name", table_name="clinics")
    op.drop_index("ix_clinics_city", table_name="clinics")
    op.drop_table("clinics")

    op.drop_table("service_categories")

    op.drop_index("ix_data_sources_type", table_name="data_sources")
    op.drop_table("data_sources")

    op.drop_index("ix_users_role", table_name="users")
    op.drop_table("users")
