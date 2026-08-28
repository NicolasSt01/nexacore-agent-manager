"""Shareable agent templates and clone lineage.

Revision ID: 0020_agent_templates
Revises: 0019_meta_messaging_channels
"""

from alembic import op
import sqlalchemy as sa


revision = "0020_agent_templates"
down_revision = "0019_meta_messaging_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("agents", sa.Column("template_label", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("agents", sa.Column("cloned_from_agent_id", sa.Uuid(), nullable=True))
    op.create_index("ix_agents_cloned_from_agent_id", "agents", ["cloned_from_agent_id"])
    op.create_foreign_key(
        "fk_agents_cloned_from_agent_id", "agents", "agents", ["cloned_from_agent_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_agents_cloned_from_agent_id", "agents", type_="foreignkey")
    op.drop_index("ix_agents_cloned_from_agent_id", table_name="agents")
    op.drop_column("agents", "cloned_from_agent_id")
    op.drop_column("agents", "template_label")
    op.drop_column("agents", "is_template")
