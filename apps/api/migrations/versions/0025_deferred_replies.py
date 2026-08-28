"""Deferred replies: wait for the contact to finish writing before answering.

Revision ID: 0025_deferred_replies
Revises: 0024_contact_summary
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_deferred_replies"
down_revision = "0024_contact_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("reply_delay_seconds", sa.Integer(), nullable=False, server_default="8"))
    op.add_column("conversations", sa.Column("reply_due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_conversations_reply_due_at", "conversations", ["reply_due_at"])


def downgrade() -> None:
    op.drop_index("ix_conversations_reply_due_at", table_name="conversations")
    op.drop_column("conversations", "reply_due_at")
    op.drop_column("agents", "reply_delay_seconds")
