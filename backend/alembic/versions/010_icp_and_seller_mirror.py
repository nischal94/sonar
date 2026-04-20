"""Add icp, seller_mirror, and their embeddings to capability_profile_versions (Phase 2.6).

Revision ID: 010
Revises: 009
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capability_profile_versions", sa.Column("icp", sa.Text(), nullable=True)
    )
    op.add_column(
        "capability_profile_versions",
        sa.Column("seller_mirror", sa.Text(), nullable=True),
    )
    op.add_column(
        "capability_profile_versions",
        sa.Column("icp_embedding", Vector(1536), nullable=True),
    )
    op.add_column(
        "capability_profile_versions",
        sa.Column("seller_mirror_embedding", Vector(1536), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capability_profile_versions", "seller_mirror_embedding")
    op.drop_column("capability_profile_versions", "icp_embedding")
    op.drop_column("capability_profile_versions", "seller_mirror")
    op.drop_column("capability_profile_versions", "icp")
