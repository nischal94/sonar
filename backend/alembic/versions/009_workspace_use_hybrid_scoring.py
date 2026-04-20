"""workspaces.use_hybrid_scoring — feature flag for Phase 2.6 hybrid scorer.

When FALSE (the default for every existing row), the pipeline uses the
legacy compute_combined_score (relevance × relationship × timing). When
TRUE, the pipeline uses compute_hybrid_score (fit × intent) and reads
connection.fit_score + profile.icp_embedding + profile.seller_mirror_embedding.

Rollout: new workspaces default to FALSE. Operators flip per-workspace
after running /profile/extract (populates ICP + seller_mirror embeddings)
and scripts/backfill_fit_scores.py (populates connection.fit_score). After
the dogfood workspace is stable for one release cycle, a future migration
can switch the column default to TRUE and the legacy scorer can be retired.

NOT NULL with server_default=false so the migration runs in O(1) on
existing rows (no table rewrite). See docs/phase-2-6/design.md §3.7.

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
