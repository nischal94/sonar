"""workspace.backfill_failed_at — terminal failure state for day-one backfill

Revision ID: 006
Revises: 005
Create Date: 2026-04-18
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("backfill_failed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "backfill_failed_at")
