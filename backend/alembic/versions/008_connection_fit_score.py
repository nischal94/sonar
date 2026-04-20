"""Add fit_score to connections (Phase 2.6).

Revision ID: 008
Revises: 007
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "connections",
        sa.Column("fit_score", sa.REAL(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connections", "fit_score")
