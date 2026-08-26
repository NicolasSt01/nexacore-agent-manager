"""Billing configuration per client, seller ownership and per-client usage.

Revision ID: 0018_billing_and_seller_scoping
Revises: 0017_whatsapp_cloud_channel
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_billing_and_seller_scoping"
down_revision = "0017_whatsapp_cloud_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Client: seller ownership + billing configuration ------------------
    op.add_column("clients", sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
    op.create_index("ix_clients_created_by_user_id", "clients", ["created_by_user_id"])
    op.create_foreign_key(
        "fk_clients_created_by_user_id", "clients", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("clients", sa.Column("billing_mode", sa.String(30), nullable=False, server_default="plan"))
    op.add_column(
        "clients", sa.Column("monthly_fee_mxn", sa.Numeric(10, 2), nullable=False, server_default="200.00")
    )
    op.add_column(
        "clients", sa.Column("monthly_token_limit", sa.Integer(), nullable=False, server_default="500000")
    )
    op.add_column("clients", sa.Column("billing_anchor_day", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("clients", sa.Column("encrypted_client_api_key", sa.Text(), nullable=True))

    # Existing clients cut on the day they were registered, matching the rule
    # applied to every client created from now on.
    op.execute("UPDATE clients SET billing_anchor_day = EXTRACT(DAY FROM created_at)")

    # Pre-existing clients predate sellers: hand them to the agency owner so
    # they stay visible instead of becoming orphaned rows nobody can see.
    op.execute(
        """
        UPDATE clients
        SET created_by_user_id = (
            SELECT u.id FROM users u
            WHERE u.agency_id = clients.agency_id
            ORDER BY u.created_at ASC
            LIMIT 1
        )
        WHERE created_by_user_id IS NULL
        """
    )

    # --- ProviderCredential: per-credential base URL -----------------------
    op.add_column("provider_credentials", sa.Column("base_url", sa.Text(), nullable=True))

    # --- UsageRecord: attribute usage to a client, not just an agent -------
    op.add_column("usage_records", sa.Column("client_id", sa.Uuid(), nullable=True))
    op.add_column("usage_records", sa.Column("source", sa.String(20), nullable=False, server_default=""))
    op.execute(
        """
        UPDATE usage_records
        SET client_id = (SELECT a.client_id FROM agents a WHERE a.id = usage_records.agent_id)
        WHERE client_id IS NULL AND agent_id IS NOT NULL
        """
    )
    # Rows whose agent was already deleted cannot be attributed to a client and
    # would block the NOT NULL below. They carry no recoverable billing meaning.
    op.execute("DELETE FROM usage_records WHERE client_id IS NULL")
    op.alter_column("usage_records", "client_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_usage_records_client_id", "usage_records", ["client_id"])
    op.create_index("ix_usage_records_client_created", "usage_records", ["client_id", "created_at"])
    op.create_foreign_key(
        "fk_usage_records_client_id", "usage_records", "clients", ["client_id"], ["id"], ondelete="CASCADE"
    )

    # --- Roles -------------------------------------------------------------
    # "admin" predates the role system and meant "agency owner"; make that
    # explicit so authorization reads the same everywhere.
    op.execute("UPDATE users SET role = 'superadmin' WHERE role = 'admin'")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'superadmin'")

    op.drop_constraint("fk_usage_records_client_id", "usage_records", type_="foreignkey")
    op.drop_index("ix_usage_records_client_created", table_name="usage_records")
    op.drop_index("ix_usage_records_client_id", table_name="usage_records")
    op.drop_column("usage_records", "source")
    op.drop_column("usage_records", "client_id")

    op.drop_column("provider_credentials", "base_url")

    op.drop_constraint("fk_clients_created_by_user_id", "clients", type_="foreignkey")
    op.drop_index("ix_clients_created_by_user_id", table_name="clients")
    op.drop_column("clients", "encrypted_client_api_key")
    op.drop_column("clients", "billing_anchor_day")
    op.drop_column("clients", "monthly_token_limit")
    op.drop_column("clients", "monthly_fee_mxn")
    op.drop_column("clients", "billing_mode")
    op.drop_column("clients", "created_by_user_id")
