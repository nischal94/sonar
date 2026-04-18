"""workspace backfill columns — day-one backfill bookkeeping

Revision ID: 005
Revises: 004
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("backfill_started_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column("backfill_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "backfill_profile_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "backfill_profile_count")
    op.drop_column("workspaces", "backfill_completed_at")
    op.drop_column("workspaces", "backfill_started_at")
