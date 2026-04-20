"""Add use_hybrid_scoring flag to workspaces (Phase 2.6).

Revision ID: 009
Revises: 008
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "use_hybrid_scoring",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "use_hybrid_scoring")
