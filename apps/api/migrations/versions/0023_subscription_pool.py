"""Shared subscription pool: usage snapshots and circuit-breaker thresholds.

Revision ID: 0023_subscription_pool
Revises: 0022_conversation_memory
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_subscription_pool"
down_revision = "0022_conversation_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("windows", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("tokens_at_capture", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_usage_agency_id", "subscription_usage", ["agency_id"])
    op.create_index("ix_subscription_usage_captured_at", "subscription_usage", ["captured_at"])
    op.create_index(
        "ix_subscription_usage_lookup", "subscription_usage", ["agency_id", "provider", "captured_at"]
    )

    for column, kind, default in (
        ("pool_degrade_percent", sa.Integer(), "80"),
        ("pool_block_percent", sa.Integer(), "95"),
        ("pool_alert_percent", sa.Integer(), "70"),
    ):
        op.add_column("agency_settings", sa.Column(column, kind, nullable=False, server_default=default))
    op.add_column(
        "agency_settings", sa.Column("pool_fallback_model", sa.String(length=180), nullable=False, server_default="")
    )
    op.add_column("agency_settings", sa.Column("pool_alerted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in (
        "pool_alerted_at",
        "pool_fallback_model",
        "pool_alert_percent",
        "pool_block_percent",
        "pool_degrade_percent",
    ):
        op.drop_column("agency_settings", column)
    op.drop_index("ix_subscription_usage_lookup", table_name="subscription_usage")
    op.drop_index("ix_subscription_usage_captured_at", table_name="subscription_usage")
    op.drop_index("ix_subscription_usage_agency_id", table_name="subscription_usage")
    op.drop_table("subscription_usage")
