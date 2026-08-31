"""What the conversation was about, carried into the appointment emails.

Revision ID: 0027_appointment_summary
Revises: 0026_appointments
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_appointment_summary"
down_revision = "0026_appointments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("summary", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("appointments", "summary")
