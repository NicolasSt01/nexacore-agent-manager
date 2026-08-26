"""Facebook Messenger and Instagram Direct channels (Meta Messenger Platform).

Revision ID: 0019_meta_messaging_channels
Revises: 0018_billing_and_seller_scoping
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_meta_messaging_channels"
down_revision = "0018_billing_and_seller_scoping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_messaging_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="disconnected"),
        sa.Column("account_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("account_name", sa.String(length=180), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_app_secret", sa.Text(), nullable=True),
        sa.Column("webhook_verify_token", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "platform", name="uq_meta_channels_client_platform"),
    )
    op.create_index("ix_meta_messaging_channels_agency_id", "meta_messaging_channels", ["agency_id"])
    op.create_index("ix_meta_messaging_channels_client_id", "meta_messaging_channels", ["client_id"])
    op.create_index("ix_meta_messaging_channels_agent_id", "meta_messaging_channels", ["agent_id"])

    op.add_column("conversations", sa.Column("meta_channel_id", sa.Uuid(), nullable=True))
    op.create_index("ix_conversations_meta_channel_id", "conversations", ["meta_channel_id"])
    op.create_foreign_key(
        "fk_conversations_meta_channel_id",
        "conversations",
        "meta_messaging_channels",
        ["meta_channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_conversations_meta_chat", "conversations", ["meta_channel_id", "external_chat_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_conversations_meta_chat", "conversations", type_="unique")
    op.drop_constraint("fk_conversations_meta_channel_id", "conversations", type_="foreignkey")
    op.drop_index("ix_conversations_meta_channel_id", table_name="conversations")
    op.drop_column("conversations", "meta_channel_id")
    op.drop_table("meta_messaging_channels")
