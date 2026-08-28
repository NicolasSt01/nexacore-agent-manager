"""Versioned model prices, FX rates, cost snapshots and agency settings.

Revision ID: 0021_pricing_fx_and_agency_settings
Revises: 0020_agent_templates
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_pricing_fx_and_agency_settings"
down_revision = "0020_agent_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Versioned prices --------------------------------------------------
    op.create_table(
        "model_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=180), nullable=False),
        sa.Column("input_price_per_1k_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("output_price_per_1k_usd", sa.Numeric(12, 8), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model", "effective_from", name="uq_model_prices_provider_model_from"),
    )
    op.create_index("ix_model_prices_effective_from", "model_prices", ["effective_from"])
    op.create_index("ix_model_prices_lookup", "model_prices", ["provider", "model", "effective_from"])

    # --- FX ----------------------------------------------------------------
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("base", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("quote", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("rate", sa.Numeric(12, 6), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="banxico_fix"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("base", "quote", "rate_date", name="uq_fx_rates_pair_date"),
    )
    op.create_index("ix_fx_rates_rate_date", "fx_rates", ["rate_date"])

    # --- Immutable cost snapshot on usage ----------------------------------
    for column, kind, default in (
        ("input_price_per_1k_usd", sa.Numeric(12, 8), "0"),
        ("output_price_per_1k_usd", sa.Numeric(12, 8), "0"),
        ("cost_usd", sa.Numeric(14, 8), "0"),
        ("usd_to_mxn", sa.Numeric(12, 6), "0"),
        ("cost_mxn", sa.Numeric(14, 6), "0"),
    ):
        op.add_column("usage_records", sa.Column(column, kind, nullable=False, server_default=default))
    # Existing rows predate cost accounting: mark them so finance can report
    # them as unpriced instead of silently counting them as zero-cost.
    op.add_column(
        "usage_records", sa.Column("price_source", sa.String(length=20), nullable=False, server_default="unknown")
    )

    # --- Quota notification stamps ----------------------------------------
    op.add_column("clients", sa.Column("quota_warned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("clients", sa.Column("quota_blocked_at", sa.DateTime(timezone=True), nullable=True))

    # --- Agency settings (SMTP + notification toggles) ---------------------
    op.create_table(
        "agency_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("emails_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("smtp_host", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_user", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("encrypted_smtp_password", sa.Text(), nullable=True),
        sa.Column("smtp_use_tls", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("smtp_from_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("smtp_from_name", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("owner_alert_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("notify_seller_on_quota", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notify_client_on_quota", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", name="uq_agency_settings_agency"),
    )
    op.create_index("ix_agency_settings_agency_id", "agency_settings", ["agency_id"])


def downgrade() -> None:
    op.drop_index("ix_agency_settings_agency_id", table_name="agency_settings")
    op.drop_table("agency_settings")
    op.drop_column("clients", "quota_blocked_at")
    op.drop_column("clients", "quota_warned_at")
    for column in (
        "price_source",
        "cost_mxn",
        "usd_to_mxn",
        "cost_usd",
        "output_price_per_1k_usd",
        "input_price_per_1k_usd",
    ):
        op.drop_column("usage_records", column)
    op.drop_index("ix_fx_rates_rate_date", table_name="fx_rates")
    op.drop_table("fx_rates")
    op.drop_index("ix_model_prices_lookup", table_name="model_prices")
    op.drop_index("ix_model_prices_effective_from", table_name="model_prices")
    op.drop_table("model_prices")
