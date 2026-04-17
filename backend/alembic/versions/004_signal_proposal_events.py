"""signal_proposal_events — telemetry for wizard LLM calls

Revision ID: 004
Revises: 003
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_proposal_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("what_you_sell", sa.Text(), nullable=False),
        sa.Column("icp", sa.Text(), nullable=True),
        sa.Column("proposed", postgresql.JSONB(), nullable=False),
        sa.Column(
            "accepted_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "edited_pairs", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "rejected_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "user_added", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_signal_proposal_events_workspace_created",
        "signal_proposal_events",
        ["workspace_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_signal_proposal_events_version_completed",
        "signal_proposal_events",
        ["prompt_version", sa.text("completed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_signal_proposal_events_version_completed",
        table_name="signal_proposal_events",
    )
    op.drop_index(
        "ix_signal_proposal_events_workspace_created",
        table_name="signal_proposal_events",
    )
    op.drop_table("signal_proposal_events")
