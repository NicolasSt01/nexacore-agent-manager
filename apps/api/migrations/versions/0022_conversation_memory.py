"""Per-agent conversation memory: session gap and history age cap.

Revision ID: 0022_conversation_memory
Revises: 0021_pricing_fx_agency_settings
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_conversation_memory"
down_revision = "0021_pricing_fx_agency_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("session_gap_hours", sa.Integer(), nullable=False, server_default="6"))
    op.add_column("agents", sa.Column("history_max_age_days", sa.Integer(), nullable=False, server_default="7"))
    # New default is 20; existing agents on the old default of 30 move with it,
    # anything customised is left alone.
    op.execute("UPDATE agents SET memory_limit = 20 WHERE memory_limit = 30")
    op.alter_column("agents", "memory_limit", existing_type=sa.Integer(), server_default="20")


def downgrade() -> None:
    op.alter_column("agents", "memory_limit", existing_type=sa.Integer(), server_default="30")
    op.execute("UPDATE agents SET memory_limit = 30 WHERE memory_limit = 20")
    op.drop_column("agents", "history_max_age_days")
    op.drop_column("agents", "session_gap_hours")
