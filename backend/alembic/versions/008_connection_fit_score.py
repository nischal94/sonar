"""connections.fit_score — per-connection ICP fit for Phase 2.6 hybrid scoring.

Phase 2.6 replaces single-axis post-similarity matching with a two-axis
hybrid: final_score = fit_score × intent_score. fit_score is computed per
connection as cos(ICP, conn) - λ · cos(seller_mirror, conn), where ICP and
seller_mirror are LLM-extracted from the workspace's source text and conn
is the embedding of headline + company. Writers: the pipeline (on first
encounter of a workspace using hybrid) and scripts/backfill_fit_scores.py.

Nullable because existing workspaces on legacy scoring never populate it,
and new hybrid-workspace connections are populated lazily on first scoring.

Type matches existing relationship_score on the same table (sa.Float →
Postgres double precision) for schema consistency across connection-level
score columns.

See docs/phase-2-6/design.md §3.2.

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
        sa.Column("fit_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connections", "fit_score")
