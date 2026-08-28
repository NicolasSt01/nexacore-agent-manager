"""Contact summary: continuity across sessions without the transcript.

Revision ID: 0024_contact_summary
Revises: 0023_subscription_pool
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_contact_summary"
down_revision = "0023_subscription_pool"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("contact_summary", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "conversations", sa.Column("contact_summary_through", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("conversations", "contact_summary_through")
    op.drop_column("conversations", "contact_summary")
