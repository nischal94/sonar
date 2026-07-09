"""capability_profile_versions — add ICP + seller_mirror paragraphs + embeddings.

Phase 2.6 extracts two paragraphs from a workspace's source text via
app/prompts/extract_icp_and_seller_mirror.py:
  - icp: who the workspace's buyer is — role, seniority, company shape,
    contrastively phrased with explicit non-buyers named.
  - seller_mirror: what OTHER sellers of the same capability look like on
    LinkedIn. Subtracted from the ICP similarity during fit scoring to
    suppress competing-vendor leakage.

Both are embedded via text-embedding-3-small (1536 dims — must match the
existing `embedding` column dimension so cosine math stays consistent).

All four columns nullable: existing profile versions pre-Phase-2.6 don't
have them, and the pipeline's hybrid branch falls back to the legacy
scorer if either embedding is NULL (see app/workers/pipeline.py).

See docs/phase-2-6/design.md §3.2 + §4.3.

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
