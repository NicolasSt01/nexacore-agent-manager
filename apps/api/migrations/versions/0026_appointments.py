"""Appointment booking: per-client SMTP, agent scheduling settings, appointments.

Revision ID: 0026_appointments
Revises: 0025_deferred_replies
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_appointments"
down_revision = "0025_deferred_replies"
branch_labels = None
depends_on = None


CLIENT_COLUMNS = (
    ("notification_email", sa.String(320), True, None),
    ("smtp_enabled", sa.Boolean(), False, "false"),
    ("smtp_host", sa.String(255), False, ""),
    ("smtp_port", sa.Integer(), False, "587"),
    ("smtp_user", sa.String(255), False, ""),
    ("encrypted_smtp_password", sa.Text(), True, None),
    ("smtp_use_tls", sa.Boolean(), False, "true"),
    ("smtp_from_email", sa.String(320), False, ""),
    ("smtp_from_name", sa.String(180), False, ""),
    ("smtp_verified_at", sa.DateTime(timezone=True), True, None),
)

AGENT_COLUMNS = (
    ("scheduling_enabled", sa.Boolean(), "false"),
    ("scheduling_owner_email", sa.String(320), ""),
    ("scheduling_location", sa.String(255), ""),
    ("scheduling_duration_minutes", sa.Integer(), "60"),
    ("scheduling_hours", sa.Text(), ""),
    ("scheduling_require_email", sa.Boolean(), "true"),
)


def upgrade() -> None:
    for name, type_, nullable, default in CLIENT_COLUMNS:
        op.add_column("clients", sa.Column(name, type_, nullable=nullable, server_default=default))
    for name, type_, default in AGENT_COLUMNS:
        op.add_column("agents", sa.Column(name, type_, nullable=False, server_default=default))

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agency_id", sa.Uuid(), sa.ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_name", sa.String(180), nullable=False, server_default=""),
        sa.Column("contact_email", sa.String(320), nullable=True),
        sa.Column("contact_phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("title", sa.String(240), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("location", sa.String(255), nullable=False, server_default=""),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("public_token", sa.String(64), nullable=False, unique=True),
        sa.Column("contact_notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("owner_notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_appointments_agency_id", "appointments", ["agency_id"])
    op.create_index("ix_appointments_client_id", "appointments", ["client_id"])
    op.create_index("ix_appointments_agent_id", "appointments", ["agent_id"])
    op.create_index("ix_appointments_conversation_id", "appointments", ["conversation_id"])
    op.create_index("ix_appointments_public_token", "appointments", ["public_token"], unique=True)
    op.create_index("ix_appointments_client_starts", "appointments", ["client_id", "starts_at"])


def downgrade() -> None:
    op.drop_table("appointments")
    for name, _type, _default in AGENT_COLUMNS:
        op.drop_column("agents", name)
    for name, _type, _nullable, _default in CLIENT_COLUMNS:
        op.drop_column("clients", name)
